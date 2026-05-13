"""
Search Router - 语义检索
基于向量数据库的自然语言对话搜索
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from app.services.vector_service import search_utterances
from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Search"])


# ───────────────────────────────────────────────
# Pydantic 模型
# ───────────────────────────────────────────────


class SearchResultItem(BaseModel):
    """搜索结果项"""
    id: str
    text: str
    speaker_id: Optional[str]
    speaker_name: Optional[str]
    recording_id: str
    timestamp: Optional[str]
    emotion: Optional[str]
    similarity: float
    start_time: Optional[float]
    end_time: Optional[float]


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    results: List[SearchResultItem]
    total: int


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.get(
    "/",
    response_model=dict,
    summary="语义搜索对话",
    description="使用自然语言查询搜索历史对话片段，基于向量相似度检索",
)
async def semantic_search(
    user_id: str = Query(..., description="用户ID"),
    q: str = Query(..., description="搜索查询文本", min_length=1),
    top_k: int = Query(10, ge=1, le=50, description="返回结果数量"),
    date_from: Optional[str] = Query(None, description="起始日期 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    speaker_id: Optional[str] = Query(None, description="指定说话人筛选"),
    min_similarity: float = Query(0.5, ge=0.0, le=1.0, description="最小相似度阈值"),
):
    """
    自然语言搜索历史对话。

    使用向量嵌入技术对查询文本和历史对话进行语义匹配，
    返回最相关的对话片段。

    Args:
        user_id: 用户ID
        q: 自然语言查询文本
        top_k: 返回结果数量 (默认10)
        date_from: 起始日期过滤
        date_to: 结束日期过滤
        speaker_id: 指定说话人过滤
        min_similarity: 最小相似度阈值

    Returns:
        {
            "data": {
                "query": "查询文本",
                "results": [...],
                "total": 结果数量
            },
            "error": None
        }
    """
    try:
        # 验证查询文本
        query_text = q.strip()
        if not query_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="查询文本不能为空",
            )

        # 调用向量搜索服务
        search_results = await search_utterances(
            query=query_text,
            user_id=user_id,
            top_k=top_k,
            date_from=date_from,
            date_to=date_to,
            speaker_id=speaker_id,
            min_similarity=min_similarity,
        )

        # 补充说话人名称信息
        enriched_results = []
        speaker_cache = {}

        for item in search_results:
            spk_id = item.get("speaker_id")
            speaker_name = None

            if spk_id:
                if spk_id not in speaker_cache:
                    try:
                        row = await db.fetchrow(
                            "SELECT name FROM speakers WHERE id = $1", spk_id
                        )
                        speaker_cache[spk_id] = row.get("name") if row else None
                    except Exception:
                        speaker_cache[spk_id] = None
                speaker_name = speaker_cache.get(spk_id)

            enriched_results.append({
                "id": item.get("id"),
                "text": item.get("text"),
                "speaker_id": spk_id,
                "speaker_name": speaker_name,
                "recording_id": item.get("recording_id"),
                "timestamp": item.get("timestamp"),
                "emotion": item.get("emotion"),
                "similarity": item.get("similarity", 0.0),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            })

        return {
            "data": {
                "query": query_text,
                "results": enriched_results,
                "total": len(enriched_results),
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"语义搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}",
        )


@router.get(
    "/keywords",
    response_model=dict,
    summary="关键词搜索",
    description="使用关键词全文搜索对话片段",
)
async def keyword_search(
    user_id: str = Query(..., description="用户ID"),
    q: str = Query(..., description="关键词", min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    highlight: bool = Query(True, description="是否高亮匹配文本"),
):
    """
    关键词搜索对话片段（基于 PostgreSQL 全文搜索）。
    """
    try:
        query_text = q.strip()
        if not query_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="搜索关键词不能为空",
            )

        # 使用 ilike 进行模糊搜索
        rows = await db.fetch(
            """
            SELECT * FROM utterances
            WHERE user_id = $1 AND text ILIKE $2
            ORDER BY timestamp DESC
            LIMIT $3 OFFSET $4
            """,
            user_id, f"%{query_text}%", limit, offset,
        )

        items = [dict(row) for row in rows]

        # 高亮处理
        if highlight:
            for item in items:
                if item.get("text"):
                    item["text_highlighted"] = item["text"].replace(
                        query_text, f"**{query_text}**"
                    )

        return {
            "data": {
                "query": query_text,
                "results": items,
                "total": len(items),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"关键词搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}",
        )


@router.get(
    "/suggestions",
    response_model=dict,
    summary="搜索建议",
    description="根据部分输入提供搜索建议",
)
async def search_suggestions(
    user_id: str = Query(..., description="用户ID"),
    prefix: str = Query(..., description="输入前缀", min_length=1),
    limit: int = Query(10, ge=1, le=20),
):
    """
    获取搜索建议（基于历史对话内容）。
    """
    try:
        # 从历史对话中提取包含前缀的关键词
        rows = await db.fetch(
            """
            SELECT text FROM utterances
            WHERE user_id = $1 AND text ILIKE $2
            LIMIT 50
            """,
            user_id, f"%{prefix}%",
        )

        # 提取包含前缀的短语作为建议
        suggestions = set()
        import re
        for row in rows:
            text = row.get("text", "")
            # 匹配包含前缀的词组
            pattern = re.compile(rf'[^，。！？\s]{{0,5}}{re.escape(prefix)}[^，。！？\s]{{0,10}}', re.IGNORECASE)
            matches = pattern.findall(text)
            for match in matches:
                suggestions.add(match.strip())
                if len(suggestions) >= limit:
                    break
            if len(suggestions) >= limit:
                break

        return {
            "data": {
                "prefix": prefix,
                "suggestions": sorted(list(suggestions))[:limit],
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取搜索建议失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取建议失败: {str(e)}",
        )
