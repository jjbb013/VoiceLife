"""
Bills Router - 账单速记
管理从对话中自动提取的账单信息，支持月度统计分析
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import logging
from datetime import datetime

from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bills", tags=["Bills"])


# ───────────────────────────────────────────────
# Pydantic 模型
# ───────────────────────────────────────────────


class BillUpdate(BaseModel):
    """更新账单请求"""
    amount: Optional[float] = Field(None, ge=0, description="金额")
    category: Optional[str] = Field(None, description="消费类别")
    merchant: Optional[str] = Field(None, description="商户名称")
    note: Optional[str] = Field(None, description="备注")
    bill_date: Optional[str] = Field(None, description="账单日期 (YYYY-MM-DD)")
    is_confirmed: Optional[bool] = Field(None, description="是否确认")


# ───────────────────────────────────────────────
# 路由端点
# ───────────────────────────────────────────────


@router.get(
    "/",
    response_model=dict,
    summary="查询账单列表",
    description="获取用户的账单列表，支持月份和类别筛选",
)
async def list_bills(
    user_id: str = Query(..., description="用户ID"),
    month: Optional[str] = Query(None, description="月份 (YYYY-MM 格式)"),
    category: Optional[str] = Query(None, description="消费类别筛选"),
    is_confirmed: Optional[bool] = Query(None, description="是否已确认"),
    merchant: Optional[str] = Query(None, description="商户名称筛选"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    查询账单列表。

    Args:
        user_id: 用户ID
        month: 月份筛选，格式 YYYY-MM
        category: 消费类别（餐饮、交通、购物等）
        is_confirmed: 是否已确认
        merchant: 商户名称
    """
    try:
        conditions = ["user_id = $1"]
        params = [user_id]
        param_idx = 2

        # 月份筛选
        if month:
            try:
                year, mon = month.split("-")
                start_date = f"{year}-{mon}-01"
                if mon == "12":
                    end_date = f"{int(year) + 1}-01-01"
                else:
                    end_date = f"{year}-{int(mon) + 1:02d}-01"
                conditions.append(f"bill_date >= ${param_idx} AND bill_date < ${param_idx + 1}")
                params.extend([start_date, end_date])
                param_idx += 2
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="month 格式应为 YYYY-MM",
                )

        if category:
            conditions.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1
        if is_confirmed is not None:
            conditions.append(f"is_confirmed = ${param_idx}")
            params.append(is_confirmed)
            param_idx += 1
        if merchant:
            conditions.append(f"merchant ILIKE ${param_idx}")
            params.append(f"%{merchant}%")
            param_idx += 1

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM bills WHERE {where_clause} "
            f"ORDER BY bill_date DESC "
            f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        )
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取账单列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}",
        )


@router.get(
    "/summary",
    response_model=dict,
    summary="获取月度汇总统计",
    description="获取指定月份的账单汇总统计数据",
)
async def get_monthly_summary(
    user_id: str = Query(..., description="用户ID"),
    month: str = Query(..., description="月份 (YYYY-MM)"),
):
    """
    获取月度账单汇总。

    返回:
        - 总支出
        - 各类别支出统计
        - 日均消费
        - 未确认账单数
    """
    try:
        # 解析月份
        try:
            year, mon = month.split("-")
            start_date = f"{year}-{mon}-01"
            if mon == "12":
                end_date = f"{int(year) + 1}-01-01"
            else:
                end_date = f"{year}-{int(mon) + 1:02d}-01"
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="month 格式应为 YYYY-MM",
            )

        # 使用 SQL 聚合获取统计数据
        total_row = await db.fetchrow(
            """
            SELECT
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) as bill_count,
                COUNT(*) FILTER (WHERE NOT is_confirmed) as unconfirmed_count
            FROM bills
            WHERE user_id = $1 AND bill_date >= $2 AND bill_date < $3
            """,
            user_id, start_date, end_date,
        )

        category_rows = await db.fetch(
            """
            SELECT
                COALESCE(category, '未分类') as category,
                COALESCE(SUM(amount), 0) as total,
                COUNT(*) as count
            FROM bills
            WHERE user_id = $1 AND bill_date >= $2 AND bill_date < $3
            GROUP BY category
            ORDER BY SUM(amount) DESC
            """,
            user_id, start_date, end_date,
        )

        total_amount = float(dict(total_row)["total_amount"]) if total_row else 0.0
        bill_count = dict(total_row)["bill_count"] if total_row else 0
        unconfirmed_count = dict(total_row)["unconfirmed_count"] if total_row else 0

        sorted_categories = [
            {"category": dict(row)["category"], "total": float(dict(row)["total"]), "count": dict(row)["count"]}
            for row in category_rows
        ]

        # 日均消费
        try:
            from calendar import monthrange
            days_in_month = monthrange(int(year), int(mon))[1]
        except Exception:
            days_in_month = 30

        daily_avg = total_amount / days_in_month if days_in_month > 0 else 0

        return {
            "data": {
                "month": month,
                "total_amount": round(total_amount, 2),
                "bill_count": bill_count,
                "daily_average": round(daily_avg, 2),
                "unconfirmed_count": unconfirmed_count,
                "category_breakdown": sorted_categories,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取月度汇总失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取汇总失败: {str(e)}",
        )


@router.get(
    "/categories",
    response_model=dict,
    summary="获取所有消费类别",
    description="获取用户的所有账单消费类别",
)
async def list_categories(user_id: str = Query(..., description="用户ID")):
    """
    获取用户的所有消费类别。
    """
    try:
        rows = await db.fetch(
            "SELECT DISTINCT category FROM bills WHERE user_id = $1 AND category IS NOT NULL",
            user_id,
        )

        categories = sorted([dict(row)["category"] for row in rows if dict(row)["category"]])

        return {
            "data": categories,
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取类别失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取类别失败: {str(e)}",
        )


@router.put(
    "/{bill_id}",
    response_model=dict,
    summary="更新账单",
    description="更新账单信息，如金额、类别、商户等",
)
async def update_bill(bill_id: str, req: BillUpdate):
    """
    更新账单。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM bills WHERE id = $1",
            bill_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账单不存在: {bill_id}",
            )

        update_data = {"updated_at": datetime.utcnow().isoformat()}
        if req.amount is not None:
            update_data["amount"] = req.amount
        if req.category is not None:
            update_data["category"] = req.category
        if req.merchant is not None:
            update_data["merchant"] = req.merchant
        if req.note is not None:
            update_data["note"] = req.note
        if req.bill_date is not None:
            update_data["bill_date"] = req.bill_date
        if req.is_confirmed is not None:
            update_data["is_confirmed"] = req.is_confirmed

        if len(update_data) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供要更新的字段",
            )

        keys = list(update_data.keys())
        vals = list(update_data.values())
        set_clause = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(keys))

        row = await db.fetchrow(
            f"UPDATE bills SET {set_clause} WHERE id = $1 RETURNING *",
            bill_id,
            *vals,
        )

        return {"data": dict(row) if row else None, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新账单失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}",
        )


@router.delete(
    "/{bill_id}",
    response_model=dict,
    summary="删除账单",
    description="删除指定的账单记录",
)
async def delete_bill(bill_id: str):
    """
    删除账单。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM bills WHERE id = $1",
            bill_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账单不存在: {bill_id}",
            )

        await db.execute("DELETE FROM bills WHERE id = $1", bill_id)

        return {
            "data": {"deleted": True, "bill_id": bill_id},
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除账单失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}",
        )


@router.post(
    "/{bill_id}/confirm",
    response_model=dict,
    summary="确认账单",
    description="将账单标记为已确认",
)
async def confirm_bill(bill_id: str):
    """
    确认账单。
    """
    try:
        existing = await db.fetchrow(
            "SELECT id FROM bills WHERE id = $1",
            bill_id,
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"账单不存在: {bill_id}",
            )

        row = await db.fetchrow(
            """
            UPDATE bills
            SET is_confirmed = $2, updated_at = $3
            WHERE id = $1
            RETURNING *
            """,
            bill_id,
            True,
            datetime.utcnow().isoformat(),
        )

        return {
            "data": {
                "bill_id": bill_id,
                "is_confirmed": True,
            },
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"确认账单失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"确认失败: {str(e)}",
        )


@router.get(
    "/trend/monthly",
    response_model=dict,
    summary="获取月度消费趋势",
    description="获取用户最近几个月的消费趋势数据",
)
async def get_monthly_trend(
    user_id: str = Query(..., description="用户ID"),
    months: int = Query(6, ge=1, le=24, description="最近几个月"),
):
    """
    获取月度消费趋势。
    """
    try:
        from calendar import monthrange

        now = datetime.utcnow()
        trends = []

        for i in range(months):
            # 计算月份
            year = now.year
            mon = now.month - i
            while mon <= 0:
                mon += 12
                year -= 1

            start_date = f"{year}-{mon:02d}-01"
            if mon == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{mon + 1:02d}-01"

            row = await db.fetchrow(
                """
                SELECT
                    COALESCE(SUM(amount), 0) as total,
                    COUNT(*) as count
                FROM bills
                WHERE user_id = $1 AND bill_date >= $2 AND bill_date < $3
                """,
                user_id, start_date, end_date,
            )

            total = float(dict(row)["total"]) if row else 0
            count = dict(row)["count"] if row else 0

            trends.append({
                "month": f"{year}-{mon:02d}",
                "total_amount": round(total, 2),
                "bill_count": count,
            })

        trends.reverse()

        return {
            "data": trends,
            "error": None,
        }

    except Exception as e:
        logger.error(f"获取消费趋势失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取趋势失败: {str(e)}",
        )
