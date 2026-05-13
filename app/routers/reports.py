"""
Reports Router - 周报/日报
自动生成每日和每周的分析报告
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging
from datetime import datetime, timedelta

from app.services.llm_service import generate_daily_report
from app.services.report_generator import generate_weekly_report
from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["Reports"])


# ───────────────────────────────────────────────
# Pydantic 模型
# ───────────────────────────────────────────────


class WeeklyReportCreate(BaseModel):
    """生成周报请求"""
    user_id: str = Field(..., description="用户ID")
    week_start: Optional[str] = Field(None, description="周起始日期 (YYYY-MM-DD)，默认上周一")


class ReportUpdate(BaseModel):
    """更新报告请求"""
    title: Optional[str] = Field(None, description="报告标题")
    content: Optional[str] = Field(None, description="报告内容")
    is_archived: Optional[bool] = Field(None, description="是否归档")


# ───────────────────────────────────────────────
# 辅助函数
# ───────────────────────────────────────────────


def _get_week_range(week_start: Optional[str] = None) -> tuple:
    """获取周的起止日期"""
    if week_start:
        start = datetime.strptime(week_start, "%Y-%m-%d")
    else:
        # 默认上周一
        today = datetime.utcnow()
        days_since_monday = today.weekday()
        start = today - timedelta(days=days_since_monday + 7)

    end = start + timedelta(days=7)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _get_day_range(date_str: Optional[str] = None) -> tuple:
    """获取日的起止日期"""
    if date_str:
        start = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        start = datetime.utcnow()

    end = start + timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.get(
    "/daily",
    response_model=dict,
    summary="获取日报数据",
    description="获取指定日期的日报数据，包含对话摘要、情绪统计、重要事项等",
)
async def get_daily_report(
    user_id: str = Query(..., description="用户ID"),
    date: Optional[str] = Query(None, description="日期 (YYYY-MM-DD)，默认今天"),
    generate_if_missing: bool = Query(True, description="如果不存在则自动生成"),
):
    """
    获取日报数据。

    返回内容:
        - 今日对话摘要
        - 情绪统计
        - 重要事项
        - 消费概览
        - 待办完成情况
    """
    try:
        date_str = date or datetime.utcnow().strftime("%Y-%m-%d")

        # 1. 检查是否已有日报
        existing = await db.fetchrow(
            "SELECT * FROM daily_reports WHERE user_id = $1 AND report_date = $2",
            user_id, date_str,
        )

        if existing:
            return {"data": dict(existing), "error": None}

        # 2. 如果不存在且允许自动生成
        if generate_if_missing:
            return await _generate_daily_report(user_id, date_str)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"日期 {date_str} 的日报不存在",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取日报失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取日报失败: {str(e)}",
        )


async def _generate_daily_report(user_id: str, date_str: str) -> dict:
    """生成日报的内部函数"""
    try:
        day_start, day_end = _get_day_range(date_str)

        # 1. 获取当日 utterances
        utterance_rows = await db.fetch(
            """
            SELECT * FROM utterances
            WHERE user_id = $1 AND timestamp >= $2 AND timestamp < $3
            ORDER BY timestamp ASC
            """,
            user_id, day_start, day_end,
        )
        utterances = [dict(row) for row in utterance_rows]

        # 2. 获取当日消费
        bill_rows = await db.fetch(
            """
            SELECT * FROM bills
            WHERE user_id = $1 AND bill_date >= $2 AND bill_date < $3
            """,
            user_id, day_start, day_end,
        )
        bills = [dict(row) for row in bill_rows]

        # 3. 获取待办完成情况
        todo_rows = await db.fetch(
            """
            SELECT * FROM todos
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            """,
            user_id, day_start, day_end,
        )
        todos = [dict(row) for row in todo_rows]

        completed_todos = [t for t in todos if t.get("status") == "completed"]

        # 4. 情绪统计
        emotion_stats = {}
        for u in utterances:
            emotion = u.get("emotion") or "neutral"
            emotion_stats[emotion] = emotion_stats.get(emotion, 0) + 1

        # 5. 调用 LLM 生成摘要
        summary_text = ""
        if utterances:
            try:
                summary_text = await generate_daily_report(
                    utterances=utterances,
                    bills=bills,
                    todos=todos,
                )
            except Exception as e:
                logger.warning(f"LLM 生成日报摘要失败: {e}")
                summary_text = f"今日共有 {len(utterances)} 条对话记录，{len(bills)} 笔消费。"

        # 6. 构建日报数据
        report_id = str(uuid.uuid4())
        report_data = {
            "id": report_id,
            "user_id": user_id,
            "report_date": date_str,
            "title": f"{date_str} 日报",
            "summary": summary_text,
            "utterance_count": len(utterances),
            "emotion_stats": emotion_stats,
            "total_spend": sum(b.get("amount", 0) or 0 for b in bills),
            "bill_count": len(bills),
            "todo_completed": len(completed_todos),
            "todo_total": len(todos),
            "details": {
                "utterances": utterances,
                "bills": bills,
                "todos": todos,
            },
            "created_at": datetime.utcnow().isoformat(),
        }

        # 7. 保存到数据库
        try:
            await db.fetchrow(
                """
                INSERT INTO daily_reports
                    (id, user_id, report_date, title, summary, utterance_count,
                     emotion_stats, total_spend, bill_count, todo_completed,
                     todo_total, details, created_at)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING *
                """,
                report_id, user_id, date_str, report_data["title"],
                summary_text, len(utterances), emotion_stats,
                report_data["total_spend"], len(bills),
                len(completed_todos), len(todos), report_data["details"],
                report_data["created_at"],
            )
        except Exception as e:
            logger.warning(f"保存日报到数据库失败: {e}")

        return {"data": report_data, "error": None}

    except Exception as e:
        logger.error(f"生成日报失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成日报失败: {str(e)}",
        )


@router.get(
    "/weekly",
    response_model=dict,
    summary="获取周报列表",
    description="获取用户的周报列表",
)
async def list_weekly_reports(
    user_id: str = Query(..., description="用户ID"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """
    获取周报列表。
    """
    try:
        rows = await db.fetch(
            """
            SELECT * FROM weekly_reports
            WHERE user_id = $1
            ORDER BY week_start DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset,
        )

        items = [dict(row) for row in rows]

        # 获取总数
        total = await db.fetchval(
            "SELECT COUNT(*) FROM weekly_reports WHERE user_id = $1",
            user_id,
        )

        return {
            "data": {
                "items": items,
                "total": total or 0,
                "limit": limit,
                "offset": offset,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取周报列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.get(
    "/weekly/{report_id}",
    response_model=dict,
    summary="获取周报详情",
    description="获取指定周报的详细内容",
)
async def get_weekly_report(report_id: str):
    """
    获取周报详情。
    """
    try:
        row = await db.fetchrow(
            "SELECT * FROM weekly_reports WHERE id = $1",
            report_id,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"周报不存在: {report_id}",
            )

        return {"data": dict(row), "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取周报失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.post(
    "/weekly",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="手动生成周报",
    description="为指定周生成周报",
)
async def create_weekly_report(req: WeeklyReportCreate):
    """
    手动生成周报。

    流程:
        1. 确定周范围
        2. 获取该周的日报数据
        3. 汇总生成周报
        4. 保存到数据库
    """
    try:
        week_start, week_end = _get_week_range(req.week_start)

        # 1. 检查是否已存在
        existing = await db.fetchrow(
            "SELECT id FROM weekly_reports WHERE user_id = $1 AND week_start = $2",
            req.user_id, week_start,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"该周({week_start})的周报已存在",
            )

        # 2. 获取该周的日报
        daily_rows = await db.fetch(
            """
            SELECT * FROM daily_reports
            WHERE user_id = $1 AND report_date >= $2 AND report_date < $3
            """,
            req.user_id, week_start, week_end,
        )
        daily_list = [dict(row) for row in daily_rows]

        # 3. 获取该周的 utterances 和 bills
        utterance_rows = await db.fetch(
            """
            SELECT * FROM utterances
            WHERE user_id = $1 AND timestamp >= $2 AND timestamp < $3
            """,
            req.user_id, week_start, week_end,
        )
        utterances = [dict(row) for row in utterance_rows]

        bill_rows = await db.fetch(
            """
            SELECT * FROM bills
            WHERE user_id = $1 AND bill_date >= $2 AND bill_date < $3
            """,
            req.user_id, week_start, week_end,
        )
        bills = [dict(row) for row in bill_rows]

        # 4. 调用服务生成周报
        try:
            weekly_content = await generate_weekly_report(
                daily_reports=daily_list,
                utterances=utterances,
                bills=bills,
                week_start=week_start,
            )
        except Exception as e:
            logger.warning(f"LLM 生成周报失败: {e}")
            weekly_content = {
                "summary": f"本周共有 {len(utterances)} 条对话记录，{len(bills)} 笔消费。",
                "highlights": [],
                "recommendations": [],
            }

        # 5. 汇总统计
        total_utterances = len(utterances)
        total_spend = sum(b.get("amount", 0) or 0 for b in bills)
        total_bills = len(bills)

        # 情绪汇总
        emotion_stats = {}
        for u in utterances:
            emotion = u.get("emotion") or "neutral"
            emotion_stats[emotion] = emotion_stats.get(emotion, 0) + 1

        # 6. 保存周报
        report_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        report_data = {
            "id": report_id,
            "user_id": req.user_id,
            "week_start": week_start,
            "week_end": week_end,
            "title": f"{week_start} 周报",
            "summary": weekly_content.get("summary", "") if isinstance(weekly_content, dict) else str(weekly_content),
            "highlights": weekly_content.get("highlights", []) if isinstance(weekly_content, dict) else [],
            "recommendations": weekly_content.get("recommendations", []) if isinstance(weekly_content, dict) else [],
            "total_utterances": total_utterances,
            "total_spend": total_spend,
            "total_bills": total_bills,
            "emotion_stats": emotion_stats,
            "created_at": now,
        }

        row = await db.fetchrow(
            """
            INSERT INTO weekly_reports
                (id, user_id, week_start, week_end, title, summary,
                 highlights, recommendations, total_utterances, total_spend,
                 total_bills, emotion_stats, created_at)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
            """,
            report_id, req.user_id, week_start, week_end,
            report_data["title"], report_data["summary"],
            report_data["highlights"], report_data["recommendations"],
            total_utterances, total_spend, total_bills,
            emotion_stats, now,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存周报失败",
            )

        return {
            "data": dict(row),
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成周报失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成周报失败: {str(e)}",
        )


@router.put(
    "/weekly/{report_id}",
    response_model=dict,
    summary="更新周报",
    description="更新周报的标题或内容",
)
async def update_weekly_report(report_id: str, req: ReportUpdate):
    """
    更新周报。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM weekly_reports WHERE id = $1",
            report_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"周报不存在: {report_id}",
            )

        update_data = {"updated_at": datetime.utcnow().isoformat()}
        if req.title is not None:
            update_data["title"] = req.title
        if req.content is not None:
            update_data["content"] = req.content
        if req.is_archived is not None:
            update_data["is_archived"] = req.is_archived

        if len(update_data) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段",
            )

        keys = list(update_data.keys())
        vals = list(update_data.values())
        set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(keys))

        row = await db.fetchrow(
            f"UPDATE weekly_reports SET {set_clause} WHERE id = $1 RETURNING *",
            report_id,
            *vals,
        )

        return {"data": dict(row) if row else None, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新周报失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}",
        )


@router.delete(
    "/weekly/{report_id}",
    response_model=dict,
    summary="删除周报",
    description="删除指定的周报",
)
async def delete_weekly_report(report_id: str):
    """
    删除周报。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM weekly_reports WHERE id = $1",
            report_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"周报不存在: {report_id}",
            )

        await db.execute("DELETE FROM weekly_reports WHERE id = $1", report_id)

        return {
            "data": {"deleted": True, "report_id": report_id},
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除周报失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}",
        )


@router.get(
    "/overview",
    response_model=dict,
    summary="获取数据概览",
    description="获取用户的数据概览统计",
)
async def get_overview(
    user_id: str = Query(..., description="用户ID"),
    days: int = Query(7, ge=1, le=30, description="最近几天"),
):
    """
    获取数据概览。
    """
    try:
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        # 对话数
        utterances_count = await db.fetchval(
            """
            SELECT COUNT(*) FROM utterances
            WHERE user_id = $1 AND timestamp >= $2
            """,
            user_id, since,
        )

        # 消费金额
        total_spend = await db.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0) FROM bills
            WHERE user_id = $1 AND bill_date >= $2
            """,
            user_id, since,
        )

        # 闪念数
        memos_count = await db.fetchval(
            """
            SELECT COUNT(*) FROM flash_memos
            WHERE user_id = $1 AND created_at >= $2
            """,
            user_id, since,
        )

        # 说话人数
        speakers_count = await db.fetchval(
            """
            SELECT COUNT(*) FROM speakers
            WHERE user_id = $1
            """,
            user_id,
        )

        # 待办数
        pending_todos = await db.fetchval(
            """
            SELECT COUNT(*) FROM todos
            WHERE user_id = $1 AND status = 'pending'
            """,
            user_id,
        )

        return {
            "data": {
                "period_days": days,
                "utterances_count": utterances_count or 0,
                "total_spend": round(float(total_spend or 0), 2),
                "memos_count": memos_count or 0,
                "speakers_count": speakers_count or 0,
                "pending_todos": pending_todos or 0,
            },
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取数据概览失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取概览失败: {str(e)}",
        )
