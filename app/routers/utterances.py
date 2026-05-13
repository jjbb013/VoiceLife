"""
Utterances Router - 对话片段查询
提供对转写后的对话片段 (utterances) 的各种查询接口
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/utterances", tags=["Utterances"])


# ───────────────────────────────────────────────
# Pydantic 模型
# ───────────────────────────────────────────────


class UtteranceUpdate(BaseModel):
    """更新对话片段请求模型"""
    text: Optional[str] = Field(None, description="转写文本")
    speaker_id: Optional[str] = Field(None, description="说话人ID")
    emotion: Optional[str] = Field(None, description="情绪标签")
    is_important: Optional[bool] = Field(None, description="是否重要")
    tags: Optional[List[str]] = Field(None, description="标签列表")


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.get(
    "/",
    response_model=dict,
    summary="查询对话片段列表",
    description="支持多种条件筛选查询 utterances",
)
async def list_utterances(
    user_id: Optional[str] = Query(None, description="用户ID"),
    recording_id: Optional[str] = Query(None, description="录音ID"),
    speaker_id: Optional[str] = Query(None, description="说话人ID"),
    is_important: Optional[bool] = Query(None, description="仅重要片段"),
    emotion: Optional[str] = Query(None, description="情绪筛选"),
    has_action_item: Optional[bool] = Query(None, description="有待办事项"),
    date_from: Optional[str] = Query(None, description="起始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="文本搜索关键词"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    order_by: str = Query("timestamp", description="排序字段"),
    order_desc: bool = Query(True, description="是否降序"),
):
    """
    查询对话片段列表，支持多种筛选条件。
    """
    try:
        # 动态构建 WHERE 条件
        conditions = []
        params: list = []
        param_idx = 1

        if user_id:
            conditions.append(f"user_id = ${param_idx}")
            params.append(user_id)
            param_idx += 1
        if recording_id:
            conditions.append(f"recording_id = ${param_idx}")
            params.append(recording_id)
            param_idx += 1
        if speaker_id:
            conditions.append(f"speaker_id = ${param_idx}")
            params.append(speaker_id)
            param_idx += 1
        if is_important is not None:
            conditions.append(f"is_important = ${param_idx}")
            params.append(is_important)
            param_idx += 1
        if emotion:
            conditions.append(f"emotion = ${param_idx}")
            params.append(emotion)
            param_idx += 1
        if has_action_item is not None:
            conditions.append(f"has_action_item = ${param_idx}")
            params.append(has_action_item)
            param_idx += 1
        if date_from:
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(date_from)
            param_idx += 1
        if date_to:
            conditions.append(f"timestamp <= ${param_idx}")
            params.append(date_to)
            param_idx += 1
        if search:
            conditions.append(f"text ILIKE ${param_idx}")
            params.append(f"%{search}%")
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        # 排序方向
        direction = "DESC" if order_desc else "ASC"
        # 防止 SQL 注入：只允许已知字段
        allowed_order_fields = {"timestamp", "start_time", "end_time", "created_at", "updated_at"}
        safe_order_by = order_by if order_by in allowed_order_fields else "timestamp"

        sql = f"""
            SELECT * FROM utterances
            WHERE {where_clause}
            ORDER BY {safe_order_by} {direction}
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(sql, *params)
        items = [dict(row) for row in rows]

        return {
            "data": {
                "items": items,
                "count": len(items),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"查询 utterances 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {str(e)}",
        )


@router.get(
    "/{utterance_id}",
    response_model=dict,
    summary="获取单条对话片段",
    description="获取指定 ID 的对话片段详情",
)
async def get_utterance(utterance_id: str):
    """
    获取单条 utterance 详情。
    """
    try:
        row = await db.fetchrow(
            "SELECT * FROM utterances WHERE id = $1", utterance_id
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"对话片段不存在: {utterance_id}",
            )

        return {"data": dict(row), "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 utterance 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.get(
    "/recording/{recording_id}",
    response_model=dict,
    summary="获取录音的所有对话片段",
    description="获取某录音文件下的所有 utterances",
)
async def get_recording_utterances(
    recording_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    获取某录音的所有对话片段。
    """
    try:
        # 验证 recording 存在
        recording = await db.fetchrow(
            "SELECT id, filename, status FROM recordings WHERE id = $1", recording_id
        )
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"录音不存在: {recording_id}",
            )

        rows = await db.fetch(
            """
            SELECT * FROM utterances
            WHERE recording_id = $1
            ORDER BY start_time ASC
            LIMIT $2 OFFSET $3
            """,
            recording_id, limit, offset,
        )

        utterances = [dict(row) for row in rows]

        return {
            "data": {
                "recording": dict(recording),
                "utterances": utterances,
                "count": len(utterances),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取录音 utterances 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.get(
    "/speaker/{speaker_id}",
    response_model=dict,
    summary="获取说话人的所有对话片段",
    description="获取某说话人的所有 utterances，按时间排序",
)
async def get_speaker_utterances(
    speaker_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = Query(None, description="起始日期"),
    date_to: Optional[str] = Query(None, description="结束日期"),
):
    """
    获取某说话人的所有对话片段。
    """
    try:
        conditions = ["speaker_id = $1"]
        params: list = [speaker_id]
        param_idx = 2

        if date_from:
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(date_from)
            param_idx += 1
        if date_to:
            conditions.append(f"timestamp <= ${param_idx}")
            params.append(date_to)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT * FROM utterances
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(sql, *params)
        utterances = [dict(row) for row in rows]

        return {
            "data": {
                "speaker_id": speaker_id,
                "utterances": utterances,
                "count": len(utterances),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取说话人 utterances 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.put(
    "/{utterance_id}",
    response_model=dict,
    summary="更新对话片段",
    description="更新 utterance 的文本、说话人、标签等信息",
)
async def update_utterance(utterance_id: str, req: UtteranceUpdate):
    """
    更新对话片段信息。
    """
    try:
        # 检查存在性
        existing = await db.fetchrow(
            "SELECT id FROM utterances WHERE id = $1", utterance_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"对话片段不存在: {utterance_id}",
            )

        # 构建更新数据
        update_fields = []
        params: list = []
        param_idx = 2  # $1 is utterance_id

        if req.text is not None:
            update_fields.append(f"text = ${param_idx}")
            params.append(req.text)
            param_idx += 1
        if req.speaker_id is not None:
            update_fields.append(f"speaker_id = ${param_idx}")
            params.append(req.speaker_id)
            param_idx += 1
        if req.emotion is not None:
            update_fields.append(f"emotion = ${param_idx}")
            params.append(req.emotion)
            param_idx += 1
        if req.is_important is not None:
            update_fields.append(f"is_important = ${param_idx}")
            params.append(req.is_important)
            param_idx += 1
        if req.tags is not None:
            update_fields.append(f"tags = ${param_idx}")
            params.append(req.tags)
            param_idx += 1

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段",
            )

        set_clause = ", ".join(update_fields)
        sql = f"UPDATE utterances SET {set_clause} WHERE id = $1 RETURNING *"

        row = await db.fetchrow(sql, utterance_id, *params)

        return {"data": dict(row) if row else None, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新 utterance 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}",
        )


@router.delete(
    "/{utterance_id}",
    response_model=dict,
    summary="删除对话片段",
    description="删除指定的对话片段",
)
async def delete_utterance(utterance_id: str):
    """
    删除对话片段。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM utterances WHERE id = $1", utterance_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"对话片段不存在: {utterance_id}",
            )

        await db.execute("DELETE FROM utterances WHERE id = $1", utterance_id)

        return {"data": {"deleted": True, "utterance_id": utterance_id}, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除 utterance 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}",
        )


@router.get(
    "/timeline/{user_id}",
    response_model=dict,
    summary="获取用户对话时间线",
    description="按时间顺序获取用户的对话片段，支持日期范围筛选",
)
async def get_timeline(
    user_id: str,
    date: Optional[str] = Query(None, description="指定日期 (YYYY-MM-DD)"),
    date_from: Optional[str] = Query(None, description="起始日期"),
    date_to: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    获取用户的时间线对话片段。
    """
    try:
        conditions = ["u.user_id = $1"]
        params: list = [user_id]
        param_idx = 2

        if date:
            conditions.append(f"u.timestamp::date = ${param_idx}")
            params.append(date)
            param_idx += 1
        if date_from:
            conditions.append(f"u.timestamp >= ${param_idx}")
            params.append(date_from)
            param_idx += 1
        if date_to:
            conditions.append(f"u.timestamp <= ${param_idx}")
            params.append(date_to)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT
                u.*,
                s.name as speaker_name,
                s.relation as speaker_relation
            FROM utterances u
            LEFT JOIN speakers s ON u.speaker_id = s.id
            WHERE {where_clause}
            ORDER BY u.timestamp DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(sql, *params)
        items = [dict(row) for row in rows]

        return {
            "data": {
                "items": items,
                "count": len(items),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取时间线失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取时间线失败: {str(e)}",
        )
