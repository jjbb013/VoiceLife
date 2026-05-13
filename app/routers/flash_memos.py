"""
Flash Memos Router - 闪念胶囊
快速记录想法、备忘、灵感，支持标签和音频关联
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging
import json
from datetime import datetime

from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flash-memos", tags=["Flash Memos"])


# ───────────────────────────────────────────────
# Pydantic 模型
# ───────────────────────────────────────────────


class FlashMemoCreate(BaseModel):
    """创建闪念请求"""
    user_id: str = Field(..., description="用户ID", min_length=1)
    text: str = Field(..., description="闪念文本内容", min_length=1)
    audio_url: Optional[str] = Field(None, description="关联音频URL")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    is_pinned: bool = Field(False, description="是否置顶")


class FlashMemoUpdate(BaseModel):
    """更新闪念请求"""
    text: Optional[str] = Field(None, description="闪念文本")
    audio_url: Optional[str] = Field(None, description="关联音频URL")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    is_pinned: Optional[bool] = Field(None, description="是否置顶")
    is_archived: Optional[bool] = Field(None, description="是否归档")


class FlashMemoResponse(BaseModel):
    """闪念响应模型"""
    id: str
    user_id: str
    text: str
    audio_url: Optional[str]
    tags: Optional[List[str]]
    is_pinned: bool
    is_archived: bool
    created_at: Optional[str]
    updated_at: Optional[str]


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.get(
    "/",
    response_model=dict,
    summary="查询闪念列表",
    description="获取用户的闪念胶囊列表，支持多种筛选",
)
async def list_flash_memos(
    user_id: str = Query(..., description="用户ID"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    is_pinned: Optional[bool] = Query(None, description="按置顶筛选"),
    is_archived: Optional[bool] = Query(False, description="是否包含归档"),
    search: Optional[str] = Query(None, description="文本搜索"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    查询闪念列表。
    """
    try:
        conditions = ["user_id = $1"]
        params = [user_id]
        param_idx = 2

        # 默认不显示归档的
        if not is_archived:
            conditions.append(f"is_archived = ${param_idx}")
            params.append(False)
            param_idx += 1

        # 其他筛选
        if tag:
            conditions.append(f"tags @> ${param_idx}::jsonb")
            params.append(json.dumps([tag]))
            param_idx += 1
        if is_pinned is not None:
            conditions.append(f"is_pinned = ${param_idx}")
            params.append(is_pinned)
            param_idx += 1
        if search:
            conditions.append(f"text ILIKE ${param_idx}")
            params.append(f"%{search}%")
            param_idx += 1

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM flash_memos WHERE {where_clause} "
            f"ORDER BY is_pinned DESC, created_at DESC "
            f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        )
        params.extend([limit, offset])

        rows = await db.fetch(sql, *params)
        items = [dict(row) for row in rows]

        return {
            "data": {
                "items": items,
                "total": len(items),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取闪念列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="创建闪念",
    description="创建新的闪念胶囊",
)
async def create_flash_memo(req: FlashMemoCreate):
    """
    创建闪念胶囊。
    """
    try:
        memo_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        row = await db.fetchrow(
            """
            INSERT INTO flash_memos
                (id, user_id, text, audio_url, tags, is_pinned, is_archived, created_at, updated_at)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            memo_id,
            req.user_id,
            req.text,
            req.audio_url,
            req.tags or [],
            req.is_pinned,
            False,
            now,
            now,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建闪念失败",
            )

        return {
            "data": dict(row),
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建闪念失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建闪念失败: {str(e)}",
        )


@router.get(
    "/{memo_id}",
    response_model=dict,
    summary="获取单条闪念",
    description="获取指定闪念胶囊的详情",
)
async def get_flash_memo(memo_id: str):
    """
    获取单条闪念详情。
    """
    try:
        row = await db.fetchrow(
            "SELECT * FROM flash_memos WHERE id = $1",
            memo_id,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"闪念不存在: {memo_id}",
            )

        return {"data": dict(row), "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取闪念失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.put(
    "/{memo_id}",
    response_model=dict,
    summary="更新闪念",
    description="更新闪念胶囊的内容、标签、置顶状态等",
)
async def update_flash_memo(memo_id: str, req: FlashMemoUpdate):
    """
    更新闪念。
    """
    try:
        # 检查存在性
        existing = await db.fetchrow(
            "SELECT id FROM flash_memos WHERE id = $1",
            memo_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"闪念不存在: {memo_id}",
            )

        # 构建更新数据
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        if req.text is not None:
            update_data["text"] = req.text
        if req.audio_url is not None:
            update_data["audio_url"] = req.audio_url
        if req.tags is not None:
            update_data["tags"] = req.tags
        if req.is_pinned is not None:
            update_data["is_pinned"] = req.is_pinned
        if req.is_archived is not None:
            update_data["is_archived"] = req.is_archived

        if len(update_data) <= 1:  # 只有 updated_at
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段",
            )

        keys = list(update_data.keys())
        vals = list(update_data.values())
        set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(keys))

        row = await db.fetchrow(
            f"UPDATE flash_memos SET {set_clause} WHERE id = $1 RETURNING *",
            memo_id,
            *vals,
        )

        return {"data": dict(row) if row else None, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新闪念失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}",
        )


@router.delete(
    "/{memo_id}",
    response_model=dict,
    summary="删除闪念",
    description="删除指定的闪念胶囊",
)
async def delete_flash_memo(memo_id: str):
    """
    删除闪念。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM flash_memos WHERE id = $1",
            memo_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"闪念不存在: {memo_id}",
            )

        await db.execute("DELETE FROM flash_memos WHERE id = $1", memo_id)

        return {
            "data": {"deleted": True, "memo_id": memo_id},
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除闪念失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}",
        )


@router.post(
    "/{memo_id}/pin",
    response_model=dict,
    summary="置顶/取消置顶闪念",
    description="切换闪念的置顶状态",
)
async def toggle_pin(memo_id: str):
    """
    切换闪念的置顶状态。
    """
    try:
        row = await db.fetchrow(
            "SELECT id, is_pinned FROM flash_memos WHERE id = $1",
            memo_id,
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"闪念不存在: {memo_id}",
            )

        new_pinned = not dict(row).get("is_pinned", False)

        updated = await db.fetchrow(
            """
            UPDATE flash_memos
            SET is_pinned = $2, updated_at = $3
            WHERE id = $1
            RETURNING *
            """,
            memo_id,
            new_pinned,
            datetime.utcnow().isoformat(),
        )

        return {
            "data": {
                "memo_id": memo_id,
                "is_pinned": new_pinned,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换置顶状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"操作失败: {str(e)}",
        )


@router.get(
    "/tags/all",
    response_model=dict,
    summary="获取所有标签",
    description="获取用户闪念中使用的所有标签列表",
)
async def list_all_tags(user_id: str = Query(..., description="用户ID")):
    """
    获取用户的所有闪念标签。
    """
    try:
        rows = await db.fetch(
            "SELECT tags FROM flash_memos WHERE user_id = $1",
            user_id,
        )

        tags = set()
        for row in rows:
            item_tags = dict(row).get("tags") or []
            if isinstance(item_tags, list):
                tags.update(item_tags)

        return {
            "data": sorted(list(tags)),
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取标签失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取标签失败: {str(e)}",
        )
