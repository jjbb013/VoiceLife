"""
Speakers Router - 说话人（人物）CRUD
管理声纹分离后识别的说话人信息，支持人物合并、关系标注等
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging
from datetime import datetime

from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/speakers", tags=["Speakers"])


# ───────────────────────────────────────────────
# Pydantic 请求/响应模型
# ───────────────────────────────────────────────


class SpeakerCreate(BaseModel):
    """创建说话人请求模型"""
    user_id: str = Field(..., description="所属用户ID", min_length=1)
    name: Optional[str] = Field(None, description="说话人名称")
    relation: Optional[str] = Field(None, description="与主用户关系（如：家人、同事）")
    is_master: bool = Field(False, description="是否为主用户本人")
    embedding: Optional[List[float]] = Field(None, description="声纹向量 (256维)")
    sample_count: int = Field(0, description="样本数量")


class SpeakerUpdate(BaseModel):
    """更新说话人请求模型"""
    name: Optional[str] = Field(None, description="说话人名称")
    relation: Optional[str] = Field(None, description="与主用户关系")
    is_master: Optional[bool] = Field(None, description="是否为主用户本人")
    embedding: Optional[List[float]] = Field(None, description="声纹向量")
    sample_count: Optional[int] = Field(None, description="样本数量")


class SpeakerMergeRequest(BaseModel):
    """合并说话人请求模型"""
    target_speaker_id: str = Field(..., description="合并目标说话人ID")


class SpeakerResponse(BaseModel):
    """说话人响应模型"""
    id: str
    user_id: str
    name: Optional[str]
    relation: Optional[str]
    is_master: bool
    sample_count: int
    created_at: Optional[str]
    updated_at: Optional[str]


# ───────────────────────────────────────────────
# 辅助函数
# ───────────────────────────────────────────────


def _speaker_to_response(data: dict) -> dict:
    """将数据库记录转换为响应格式（移除敏感字段如embedding）"""
    return {
        "id": data.get("id"),
        "user_id": data.get("user_id"),
        "name": data.get("name"),
        "relation": data.get("relation"),
        "is_master": data.get("is_master", False),
        "sample_count": data.get("sample_count", 0),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.get(
    "/",
    response_model=dict,
    summary="列出用户的所有说话人",
    description="获取指定用户的所有说话人列表，支持按关系筛选",
)
async def list_speakers(
    user_id: str = Query(..., description="用户ID"),
    relation: Optional[str] = Query(None, description="按关系筛选"),
    is_master: Optional[bool] = Query(None, description="按是否主用户筛选"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """
    列出某用户的所有说话人。
    """
    try:
        # 动态构建 WHERE 条件
        conditions = ["user_id = $1"]
        params: list = [user_id]
        param_idx = 2

        if relation:
            conditions.append(f"relation = ${param_idx}")
            params.append(relation)
            param_idx += 1
        if is_master is not None:
            conditions.append(f"is_master = ${param_idx}")
            params.append(is_master)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT id, user_id, name, relation, is_master, sample_count, created_at, updated_at
            FROM speakers
            WHERE {where_clause}
            ORDER BY created_at ASC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await db.fetch(sql, *params)
        speakers = [_speaker_to_response(dict(row)) for row in rows]

        # 获取总数
        count_sql = f"SELECT COUNT(*) FROM speakers WHERE {where_clause}"
        total = await db.fetchval(count_sql, *params[:-2])  # 去掉 limit/offset

        return {
            "data": {
                "items": speakers,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取说话人列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取说话人列表失败: {str(e)}",
        )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="创建说话人",
    description="创建新的说话人记录",
)
async def create_speaker(req: SpeakerCreate):
    """
    创建说话人。
    """
    try:
        speaker_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        row = await db.fetchrow(
            """
            INSERT INTO speakers (id, user_id, name, relation, is_master, embedding, sample_count, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            speaker_id, req.user_id, req.name, req.relation, req.is_master,
            req.embedding, req.sample_count, now, now,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建说话人失败",
            )

        return {
            "data": _speaker_to_response(dict(row)),
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建说话人失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建说话人失败: {str(e)}",
        )


@router.get(
    "/{speaker_id}",
    response_model=dict,
    summary="获取说话人详情",
    description="获取单个说话人的详细信息",
)
async def get_speaker(
    speaker_id: str,
    include_embedding: bool = Query(False, description="是否包含声纹向量"),
):
    """
    获取单个说话人详情。
    """
    try:
        if include_embedding:
            sql = "SELECT * FROM speakers WHERE id = $1"
        else:
            sql = """
                SELECT id, user_id, name, relation, is_master, sample_count, created_at, updated_at
                FROM speakers WHERE id = $1
            """

        row = await db.fetchrow(sql, speaker_id)

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"说话人不存在: {speaker_id}",
            )

        return {"data": dict(row), "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取说话人详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取说话人详情失败: {str(e)}",
        )


@router.put(
    "/{speaker_id}",
    response_model=dict,
    summary="更新说话人信息",
    description="更新指定说话人的信息",
)
async def update_speaker(speaker_id: str, req: SpeakerUpdate):
    """
    更新说话人信息。
    """
    try:
        # 检查说话人是否存在
        existing = await db.fetchrow(
            "SELECT id FROM speakers WHERE id = $1", speaker_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"说话人不存在: {speaker_id}",
            )

        # 构建更新数据（排除 None 值）
        update_fields = []
        params: list = []
        param_idx = 2  # $1 is speaker_id

        if req.name is not None:
            update_fields.append(f"name = ${param_idx}")
            params.append(req.name)
            param_idx += 1
        if req.relation is not None:
            update_fields.append(f"relation = ${param_idx}")
            params.append(req.relation)
            param_idx += 1
        if req.is_master is not None:
            update_fields.append(f"is_master = ${param_idx}")
            params.append(req.is_master)
            param_idx += 1
        if req.embedding is not None:
            update_fields.append(f"embedding = ${param_idx}")
            params.append(req.embedding)
            param_idx += 1
        if req.sample_count is not None:
            update_fields.append(f"sample_count = ${param_idx}")
            params.append(req.sample_count)
            param_idx += 1

        if not update_fields:
            # 没有要更新的字段，返回当前数据
            row = await db.fetchrow(
                "SELECT * FROM speakers WHERE id = $1", speaker_id
            )
            return {"data": _speaker_to_response(dict(row)) if row else None, "error": None}

        # 添加 updated_at
        update_fields.append("updated_at = NOW()")

        set_clause = ", ".join(update_fields)
        sql = f"UPDATE speakers SET {set_clause} WHERE id = $1 RETURNING *"

        row = await db.fetchrow(sql, speaker_id, *params)

        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新说话人失败",
            )

        return {
            "data": _speaker_to_response(dict(row)),
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新说话人失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新说话人失败: {str(e)}",
        )


@router.delete(
    "/{speaker_id}",
    status_code=status.HTTP_200_OK,
    response_model=dict,
    summary="删除说话人",
    description="删除指定的说话人记录及其关联数据",
)
async def delete_speaker(
    speaker_id: str,
    cascade: bool = Query(False, description="是否级联删除关联的 utterances"),
):
    """
    删除说话人。

    默认仅删除说话人记录，cascade=True 时同时删除关联 utterances。
    """
    try:
        # 检查说话人是否存在
        existing = await db.fetchrow(
            "SELECT id FROM speakers WHERE id = $1", speaker_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"说话人不存在: {speaker_id}",
            )

        # 级联删除关联的 utterances
        if cascade:
            await db.execute(
                "DELETE FROM utterances WHERE speaker_id = $1", speaker_id
            )

        # 删除说话人记录
        await db.execute("DELETE FROM speakers WHERE id = $1", speaker_id)

        return {
            "data": {"deleted": True, "speaker_id": speaker_id, "cascade": cascade},
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除说话人失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除说话人失败: {str(e)}",
        )


@router.post(
    "/{speaker_id}/merge",
    response_model=dict,
    summary="合并说话人声纹",
    description="将当前说话人合并到目标说话人，所有 utterances 归属到目标",
)
async def merge_speakers(speaker_id: str, req: SpeakerMergeRequest):
    """
    合并声纹（将未知说话人合并到已知说话人）。

    流程:
        1. 验证源和目标说话人存在
        2. 将源说话人的所有 utterances 转移到目标
        3. 删除源说话人记录
    """
    try:
        target_id = req.target_speaker_id

        if speaker_id == target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="源说话人和目标说话人不能相同",
            )

        # 1. 验证源说话人存在
        source_row = await db.fetchrow(
            "SELECT * FROM speakers WHERE id = $1", speaker_id
        )
        if not source_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"源说话人不存在: {speaker_id}",
            )
        source_data = dict(source_row)

        # 2. 验证目标说话人存在
        target_row = await db.fetchrow(
            "SELECT * FROM speakers WHERE id = $1", target_id
        )
        if not target_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"目标说话人不存在: {target_id}",
            )
        target_data = dict(target_row)

        # 3. 更新关联的 utterances：将源 speaker_id 改为目标
        transferred_count = await db.execute(
            "UPDATE utterances SET speaker_id = $1 WHERE speaker_id = $2",
            target_id, speaker_id,
        )
        # db.execute 返回操作结果字符串，需要通过查询获取实际行数
        # 重新查询转移数量
        transferred_count_result = await db.fetchval(
            "SELECT COUNT(*) FROM utterances WHERE speaker_id = $1", target_id
        )

        # 4. 更新目标说话人的 sample_count
        new_sample_count = (target_data.get("sample_count", 0) or 0) + (source_data.get("sample_count", 0) or 0)
        await db.execute(
            """
            UPDATE speakers
            SET sample_count = $1, updated_at = NOW()
            WHERE id = $2
            """,
            new_sample_count, target_id,
        )

        # 5. 删除源说话人
        await db.execute("DELETE FROM speakers WHERE id = $1", speaker_id)

        return {
            "data": {
                "merged": True,
                "source_speaker_id": speaker_id,
                "target_speaker_id": target_id,
                "transferred_utterances": transferred_count_result,
                "new_sample_count": new_sample_count,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"合并说话人失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"合并说话人失败: {str(e)}",
        )


@router.get(
    "/{speaker_id}/utterances",
    response_model=dict,
    summary="获取说话人的所有 utterances",
    description="获取指定说话人关联的所有对话片段",
)
async def get_speaker_utterances(
    speaker_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    获取某说话人的所有对话片段。
    """
    try:
        # 验证说话人存在
        speaker = await db.fetchrow(
            "SELECT id, name FROM speakers WHERE id = $1", speaker_id
        )
        if not speaker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"说话人不存在: {speaker_id}",
            )

        rows = await db.fetch(
            """
            SELECT * FROM utterances
            WHERE speaker_id = $1
            ORDER BY timestamp DESC
            LIMIT $2 OFFSET $3
            """,
            speaker_id, limit, offset,
        )

        utterances = [dict(row) for row in rows]

        return {
            "data": {
                "speaker": dict(speaker),
                "utterances": utterances,
                "total": len(utterances),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取说话人 utterances 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 utterances 失败: {str(e)}",
        )
