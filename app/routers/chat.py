"""
Chat Router - AI 聊天接口
支持长期记忆注入的 AI 对话，自动管理会话和上下文
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging
from datetime import datetime

from app.services.llm_service import chat_with_memory
from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ───────────────────────────────────────────────
# Pydantic 模型
# ───────────────────────────────────────────────


class ChatMessage(BaseModel):
    """发送聊天消息请求"""
    user_id: str = Field(..., description="用户ID", min_length=1)
    message: str = Field(..., description="用户消息内容", min_length=1)
    session_id: Optional[str] = Field(None, description="会话ID（不填则创建新会话）")


class ChatResponse(BaseModel):
    """AI 回复响应"""
    session_id: str
    message: str
    ai_reply: str
    context_used: bool
    timestamp: str


class SessionCreate(BaseModel):
    """创建会话请求"""
    user_id: str = Field(..., description="用户ID")
    title: Optional[str] = Field(None, description="会话标题")


# ───────────────────────────────────────────────
# 辅助函数
# ───────────────────────────────────────────────


async def _get_or_create_session(user_id: str, session_id: Optional[str] = None) -> str:
    """获取或创建聊天会话"""
    if session_id:
        # 验证会话存在且属于该用户
        row = await db.fetchrow(
            "SELECT id FROM chat_sessions WHERE id = $1 AND user_id = $2",
            session_id, user_id,
        )
        if row:
            return session_id
        # 会话不存在，创建新会话

    # 创建新会话
    new_session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    await db.execute(
        """
        INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        new_session_id, user_id, "新对话", now, now,
    )

    return new_session_id


async def _get_context_for_user(user_id: str) -> dict:
    """获取用户上下文信息（今日待办、高频联系人等）"""
    context = {}

    try:
        # 1. 获取今日待办
        today = datetime.utcnow().strftime("%Y-%m-%d")
        todo_rows = await db.fetch(
            """
            SELECT * FROM todos
            WHERE user_id = $1 AND due_date = $2 AND status = $3
            ORDER BY created_at DESC
            LIMIT 10
            """,
            user_id, today, "pending",
        )
        context["today_todos"] = [dict(row) for row in todo_rows]

        # 2. 获取高频联系人（最近7天对话最多的说话人）
        speaker_rows = await db.fetch(
            """
            SELECT id, name, relation FROM speakers
            WHERE user_id = $1
            LIMIT 5
            """,
            user_id,
        )
        context["frequent_contacts"] = [dict(row) for row in speaker_rows]

        # 3. 获取最近的闪念胶囊
        memo_rows = await db.fetch(
            """
            SELECT * FROM flash_memos
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 5
            """,
            user_id,
        )
        context["recent_memos"] = [dict(row) for row in memo_rows]

    except Exception as e:
        logger.warning(f"获取用户上下文失败: {e}")

    return context


async def _save_message(session_id: str, role: str, content: str) -> None:
    """保存消息到数据库"""
    try:
        await db.execute(
            """
            INSERT INTO chat_messages (id, session_id, role, content, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            str(uuid.uuid4()), session_id, role, content, datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"保存消息失败: {e}")


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.post(
    "/",
    response_model=dict,
    summary="AI 聊天",
    description="发送消息给 AI，自动注入长期记忆和上下文",
)
async def chat(req: ChatMessage):
    """
    AI 聊天，自动注入长期记忆。

    流程:
        1. 获取或创建 session
        2. 查询今日待办、高频联系人等上下文
        3. 调用 chat_with_memory() 获取 AI 回复
        4. 保存消息到数据库
        5. 返回 AI 回复
    """
    try:
        # 1. 获取或创建会话
        session_id = await _get_or_create_session(req.user_id, req.session_id)

        # 2. 获取用户上下文
        context = await _get_context_for_user(req.user_id)

        # 3. 保存用户消息
        await _save_message(session_id, "user", req.message)

        # 4. 调用 LLM 服务
        ai_reply = await chat_with_memory(
            user_id=req.user_id,
            message=req.message,
            session_id=session_id,
            context=context,
        )

        # 5. 保存 AI 回复
        await _save_message(session_id, "assistant", ai_reply)

        # 6. 更新会话时间
        await db.execute(
            "UPDATE chat_sessions SET updated_at = NOW() WHERE id = $1",
            session_id,
        )

        return {
            "data": {
                "session_id": session_id,
                "message": req.message,
                "ai_reply": ai_reply,
                "context_used": bool(context),
                "timestamp": datetime.utcnow().isoformat(),
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI 聊天失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 聊天失败: {str(e)}",
        )


@router.get(
    "/sessions",
    response_model=dict,
    summary="获取用户的聊天会话列表",
    description="获取指定用户的所有聊天会话",
)
async def list_sessions(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
):
    """
    获取用户的聊天会话列表。
    """
    try:
        rows = await db.fetch(
            """
            SELECT * FROM chat_sessions
            WHERE user_id = $1
            ORDER BY updated_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset,
        )

        sessions = [dict(row) for row in rows]

        # 获取每个会话的最后一条消息
        for session in sessions:
            try:
                last_msg = await db.fetchrow(
                    """
                    SELECT content, created_at FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    session["id"],
                )
                session["last_message"] = dict(last_msg) if last_msg else None
            except Exception:
                session["last_message"] = None

        return {
            "data": {
                "items": sessions,
                "total": len(sessions),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话列表失败: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=dict,
    summary="获取会话消息历史",
    description="获取指定会话的所有消息",
)
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
):
    """
    获取会话消息历史。
    """
    try:
        # 验证会话存在
        session = await db.fetchrow(
            "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = $1",
            session_id,
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}",
            )

        rows = await db.fetch(
            """
            SELECT * FROM chat_messages
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            session_id, limit, offset,
        )

        messages = [dict(row) for row in rows]

        return {
            "data": {
                "session": dict(session),
                "messages": messages,
                "count": len(messages),
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取消息失败: {str(e)}",
        )


@router.delete(
    "/sessions/{session_id}",
    response_model=dict,
    summary="删除会话",
    description="删除指定的聊天会话及其所有消息",
)
async def delete_session(session_id: str):
    """
    删除聊天会话。
    """
    try:
        # 验证会话存在
        session = await db.fetchrow(
            "SELECT id FROM chat_sessions WHERE id = $1", session_id
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}",
            )

        # 先删除会话的所有消息
        await db.execute(
            "DELETE FROM chat_messages WHERE session_id = $1", session_id
        )

        # 删除会话
        await db.execute(
            "DELETE FROM chat_sessions WHERE id = $1", session_id
        )

        return {
            "data": {"deleted": True, "session_id": session_id},
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除会话失败: {str(e)}",
        )


@router.put(
    "/sessions/{session_id}",
    response_model=dict,
    summary="更新会话标题",
    description="修改聊天会话的标题",
)
async def update_session(session_id: str, title: str):
    """
    更新会话标题。
    """
    try:
        session = await db.fetchrow(
            "SELECT id FROM chat_sessions WHERE id = $1", session_id
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}",
            )

        row = await db.fetchrow(
            """
            UPDATE chat_sessions
            SET title = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING *
            """,
            title, session_id,
        )

        return {"data": dict(row) if row else None, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新会话失败: {str(e)}",
        )
