"""
Meetings Router - 会议纪要
管理会议录音、自动生成会议纪要、提取行动项
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging
import json
from datetime import datetime, timedelta

from app.services.llm_service import generate_meeting_summary
from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["Meetings"])


# ───────────────────────────────────────────────
# Pydantic 模型
# ───────────────────────────────────────────────


class MeetingCreate(BaseModel):
    """创建会议请求"""
    user_id: str = Field(..., description="用户ID")
    title: Optional[str] = Field(None, description="会议标题")
    recording_id: str = Field(..., description="关联录音ID")
    participants: Optional[List[str]] = Field(None, description="参与者列表")


class MeetingUpdate(BaseModel):
    """更新会议请求"""
    title: Optional[str] = Field(None, description="会议标题")
    summary: Optional[str] = Field(None, description="会议纪要")
    action_items: Optional[List[dict]] = Field(None, description="行动项")
    participants: Optional[List[str]] = Field(None, description="参与者列表")
    status: Optional[str] = Field(None, description="会议状态")


class ActionItemCreate(BaseModel):
    """创建行动项请求"""
    content: str = Field(..., description="行动项内容")
    assignee: Optional[str] = Field(None, description="负责人")
    due_date: Optional[str] = Field(None, description="截止日期")


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.get(
    "/",
    response_model=dict,
    summary="查询会议记录列表",
    description="获取用户的会议记录列表，支持日期和状态筛选",
)
async def list_meetings(
    user_id: str = Query(..., description="用户ID"),
    status: Optional[str] = Query(None, description="会议状态筛选"),
    date_from: Optional[str] = Query(None, description="起始日期"),
    date_to: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    查询会议记录列表。
    """
    try:
        conditions = ["user_id = $1"]
        params = [user_id]
        param_idx = 2

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1
        if date_from:
            conditions.append(f"created_at >= ${param_idx}")
            params.append(date_from)
            param_idx += 1
        if date_to:
            conditions.append(f"created_at <= ${param_idx}")
            params.append(date_to)
            param_idx += 1

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM meetings WHERE {where_clause} "
            f"ORDER BY created_at DESC "
            f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        )
        params.extend([limit, offset])

        rows = await db.fetch(sql, *params)
        meetings = [dict(row) for row in rows]

        # 补充录音信息
        for meeting in meetings:
            recording_id = meeting.get("recording_id")
            if recording_id:
                try:
                    rec_row = await db.fetchrow(
                        "SELECT filename, duration, status FROM recordings WHERE id = $1",
                        recording_id,
                    )
                    meeting["recording"] = dict(rec_row) if rec_row else None
                except Exception:
                    meeting["recording"] = None

        return {
            "data": {
                "items": meetings,
                "total": len(meetings),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取会议列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.get(
    "/{meeting_id}",
    response_model=dict,
    summary="获取会议详情",
    description="获取会议详情，包括纪要、行动项和关联的 utterances",
)
async def get_meeting(meeting_id: str):
    """
    获取会议详情+纪要。
    """
    try:
        # 1. 获取会议基本信息
        meeting_row = await db.fetchrow(
            "SELECT * FROM meetings WHERE id = $1",
            meeting_id,
        )

        if not meeting_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会议不存在: {meeting_id}",
            )

        meeting = dict(meeting_row)

        # 2. 获取关联的 utterances
        utterance_rows = await db.fetch(
            "SELECT * FROM utterances WHERE recording_id = $1 ORDER BY start_time ASC",
            meeting.get("recording_id"),
        )
        meeting["utterances"] = [dict(row) for row in utterance_rows]

        # 3. 获取关联的录音信息
        if meeting.get("recording_id"):
            try:
                rec_row = await db.fetchrow(
                    "SELECT * FROM recordings WHERE id = $1",
                    meeting["recording_id"],
                )
                meeting["recording"] = dict(rec_row) if rec_row else None
            except Exception:
                meeting["recording"] = None

        # 4. 获取行动项对应的待办状态
        action_items = meeting.get("action_items") or []
        for item in action_items:
            if item.get("todo_id"):
                try:
                    todo_row = await db.fetchrow(
                        "SELECT status FROM todos WHERE id = $1",
                        item["todo_id"],
                    )
                    item["todo_status"] = dict(todo_row).get("status") if todo_row else None
                except Exception:
                    item["todo_status"] = None

        return {"data": meeting, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会议详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="创建会议记录",
    description="从录音创建会议记录",
)
async def create_meeting(req: MeetingCreate):
    """
    创建会议记录。
    """
    try:
        # 验证 recording 存在
        recording = await db.fetchrow(
            "SELECT id, user_id FROM recordings WHERE id = $1",
            req.recording_id,
        )
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"录音不存在: {req.recording_id}",
            )

        meeting_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        row = await db.fetchrow(
            """
            INSERT INTO meetings
                (id, user_id, title, recording_id, participants, status, summary, action_items, created_at, updated_at)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            meeting_id,
            req.user_id,
            req.title or "未命名会议",
            req.recording_id,
            req.participants or [],
            "pending",
            None,
            [],
            now,
            now,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建会议失败",
            )

        return {
            "data": dict(row),
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建会议失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建失败: {str(e)}",
        )


@router.post(
    "/{meeting_id}/summary",
    response_model=dict,
    summary="手动触发纪要生成",
    description="为指定会议自动生成会议纪要",
)
async def generate_summary(meeting_id: str):
    """
    手动触发纪要生成。

    流程:
        1. 获取会议信息和关联的 utterances
        2. 调用 LLM 生成纪要
        3. 保存纪要到数据库
    """
    try:
        # 1. 获取会议信息
        meeting_row = await db.fetchrow(
            "SELECT * FROM meetings WHERE id = $1",
            meeting_id,
        )
        if not meeting_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会议不存在: {meeting_id}",
            )

        meeting = dict(meeting_row)

        # 2. 获取会议的 utterances
        utterance_rows = await db.fetch(
            "SELECT * FROM utterances WHERE recording_id = $1 ORDER BY start_time ASC",
            meeting["recording_id"],
        )
        utterances = [dict(row) for row in utterance_rows]

        if not utterances:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该会议没有对话内容，无法生成纪要",
            )

        # 3. 调用 LLM 生成纪要
        summary_result = await generate_meeting_summary(
            utterances=utterances,
            title=meeting.get("title"),
        )

        # 4. 保存结果
        update_data = {
            "summary": summary_result.get("summary"),
            "action_items": summary_result.get("action_items", []),
            "status": "summarized",
            "updated_at": datetime.utcnow().isoformat(),
        }

        keys = list(update_data.keys())
        vals = list(update_data.values())
        set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(keys))

        await db.execute(
            f"UPDATE meetings SET {set_clause} WHERE id = $1",
            meeting_id,
            *vals,
        )

        return {
            "data": {
                "meeting_id": meeting_id,
                "summary": summary_result.get("summary"),
                "action_items": summary_result.get("action_items"),
                "key_points": summary_result.get("key_points", []),
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成纪要失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成纪要失败: {str(e)}",
        )


@router.post(
    "/{meeting_id}/action-items",
    response_model=dict,
    summary="将行动项转为待办",
    description="将会议的行动项转换为用户的待办事项",
)
async def convert_action_items_to_todos(meeting_id: str):
    """
    将会议行动项转为待办。
    """
    try:
        # 获取会议信息
        meeting_row = await db.fetchrow(
            "SELECT * FROM meetings WHERE id = $1",
            meeting_id,
        )
        if not meeting_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会议不存在: {meeting_id}",
            )

        meeting = dict(meeting_row)
        action_items = meeting.get("action_items") or []

        if not action_items:
            return {
                "data": {
                    "converted": 0,
                    "todo_ids": [],
                    "message": "没有行动项需要转换",
                },
                "error": None,
            }

        # 转换每个行动项为待办，使用事务确保一致性
        todo_ids = []
        now = datetime.utcnow()

        async with db.acquire() as conn:
            async with conn.transaction():
                for idx, item in enumerate(action_items):
                    if item.get("todo_id"):
                        # 已转换过，跳过
                        todo_ids.append(item["todo_id"])
                        continue

                    todo_id = str(uuid.uuid4())
                    due_date = item.get("due_date") or (now + timedelta(days=3)).strftime("%Y-%m-%d")

                    await conn.execute(
                        """
                        INSERT INTO todos
                            (id, user_id, content, status, source, due_date, created_at, updated_at)
                        VALUES
                            ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        todo_id,
                        meeting["user_id"],
                        item.get("content", "待办事项"),
                        "pending",
                        f"meeting:{meeting_id}",
                        due_date,
                        now.isoformat(),
                        now.isoformat(),
                    )
                    todo_ids.append(todo_id)

                    # 更新 action_item 的 todo_id
                    action_items[idx]["todo_id"] = todo_id

                # 更新会议记录中的 action_items
                await conn.execute(
                    """
                    UPDATE meetings
                    SET action_items = $2, updated_at = $3
                    WHERE id = $1
                    """,
                    meeting_id,
                    json.dumps(action_items),
                    now.isoformat(),
                )

        return {
            "data": {
                "converted": len(todo_ids),
                "todo_ids": todo_ids,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"转换行动项失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"转换失败: {str(e)}",
        )


@router.put(
    "/{meeting_id}",
    response_model=dict,
    summary="更新会议信息",
    description="手动更新会议的标题、纪要等信息",
)
async def update_meeting(meeting_id: str, req: MeetingUpdate):
    """
    更新会议信息。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM meetings WHERE id = $1",
            meeting_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会议不存在: {meeting_id}",
            )

        update_data = {"updated_at": datetime.utcnow().isoformat()}
        if req.title is not None:
            update_data["title"] = req.title
        if req.summary is not None:
            update_data["summary"] = req.summary
        if req.action_items is not None:
            update_data["action_items"] = req.action_items
        if req.participants is not None:
            update_data["participants"] = req.participants
        if req.status is not None:
            update_data["status"] = req.status

        if len(update_data) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段",
            )

        keys = list(update_data.keys())
        vals = list(update_data.values())
        set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(keys))

        row = await db.fetchrow(
            f"UPDATE meetings SET {set_clause} WHERE id = $1 RETURNING *",
            meeting_id,
            *vals,
        )

        return {"data": dict(row) if row else None, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会议失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}",
        )


@router.delete(
    "/{meeting_id}",
    response_model=dict,
    summary="删除会议",
    description="删除会议记录",
)
async def delete_meeting(meeting_id: str):
    """
    删除会议记录。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM meetings WHERE id = $1",
            meeting_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会议不存在: {meeting_id}",
            )

        await db.execute("DELETE FROM meetings WHERE id = $1", meeting_id)

        return {
            "data": {"deleted": True, "meeting_id": meeting_id},
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会议失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}",
        )
