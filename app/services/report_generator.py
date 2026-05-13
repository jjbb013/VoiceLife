# -*- coding: utf-8 -*-
"""
Report Generator Service

Generates weekly reports and daily summaries from user activity data.
Aggregates recordings, utterances, events, todos, and emotion data.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

try:
    from collections import Counter
except ImportError:
    from collections import Counter  # type: ignore

from app.services.llm_service import (
    generate_daily_report,
    _chat_completion,
    _chat_completion_json,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weekly report
# ---------------------------------------------------------------------------

WEEKLY_REPORT_PROMPT = """你是一个数据分析助手。请根据以下用户一周的数据，生成周报摘要。
请直接输出一段200字以内的中文总结，不需要JSON格式。
要求：
1. 总结本周的主要活动和亮点
2. 提及重要的会议和事件
3. 点明待办完成情况
4. 简要提及财务概况（如有）
5. 语气专业但不失亲切
"""


async def generate_weekly_report(
    user_id: str,
    week_start: date,
    week_end: date,
) -> Dict[str, Any]:
    """
    Generate a comprehensive weekly report for the user.

    Aggregates data from recordings, events, todos, and emotions
    to produce statistics, highlights, and trend analysis.

    Uses asyncpg for all database queries.

    Args:
        user_id: The user to generate the report for.
        week_start: Start date of the week (inclusive).
        week_end: End date of the week (inclusive).

    Returns:
        Dict containing:
            - stats (Dict): Numerical statistics.
            - highlights (List[str]): Key highlights of the week.
            - emotions (Dict[str, int]): Emotion frequency counts.
            - chart_data (Dict): Data formatted for charts.
            - summary (str): AI-generated weekly summary text.

    Raises:
        RuntimeError: If data fetching fails.
    """
    logger.info(
        "Generating weekly report for user=%s, week=%s to %s",
        user_id, week_start, week_end,
    )

    try:
        from app.db import db

        # Compute date range
        start_dt = datetime.combine(week_start, datetime.min.time())
        end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time())

        # ------------------------------------------------------------------
        # Fetch recordings
        # ------------------------------------------------------------------
        recording_rows = await db.fetch(
            """
            SELECT id, duration_sec, summary, topics, created_at
            FROM recordings
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            ORDER BY created_at DESC
            """,
            user_id, start_dt, end_dt,
        )
        recordings = [dict(r) for r in recording_rows]

        # ------------------------------------------------------------------
        # Fetch utterances for these recordings
        # ------------------------------------------------------------------
        recording_ids = [r["id"] for r in recordings]
        utterances = []
        emotions_raw = {}

        if recording_ids:
            # Fetch utterances using ANY array
            utt_rows = await db.fetch(
                """
                SELECT id, speaker, text, created_at
                FROM utterances
                WHERE recording_id = ANY($1)
                ORDER BY created_at DESC
                """,
                recording_ids,
            )
            utterances = [dict(r) for r in utt_rows]

            # Fetch emotions from utterances (emotion column)
            for u in utterances:
                emo = u.get("emotion")
                if emo:
                    emotions_raw[u.get("speaker", "unknown")] = emo

        # ------------------------------------------------------------------
        # Fetch events
        # ------------------------------------------------------------------
        evt_rows = await db.fetch(
            """
            SELECT id, title, event_date, event_type
            FROM events
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            ORDER BY event_date
            """,
            user_id, start_dt, end_dt,
        )
        events = [dict(r) for r in evt_rows]

        # ------------------------------------------------------------------
        # Fetch todos
        # ------------------------------------------------------------------
        todo_rows = await db.fetch(
            """
            SELECT id, title, status
            FROM todos
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            """,
            user_id, start_dt, end_dt,
        )
        todos = [dict(r) for r in todo_rows]

        # ------------------------------------------------------------------
        # Fetch bills
        # ------------------------------------------------------------------
        bill_rows = await db.fetch(
            """
            SELECT id, amount, currency, category
            FROM bill_notes
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            """,
            user_id, start_dt, end_dt,
        )
        bills = [dict(r) for r in bill_rows]

        # ------------------------------------------------------------------
        # Compute statistics
        # ------------------------------------------------------------------
        total_duration = sum(r.get("duration_sec", 0) or 0 for r in recordings)
        unique_speakers = set()
        for u in utterances:
            spk = u.get("speaker")
            if spk:
                unique_speakers.add(spk)

        todos_completed = sum(1 for t in todos if t.get("status") == "done")
        todos_pending = sum(1 for t in todos if t.get("status") == "pending")

        # Aggregate expenses (CNY only for simplicity)
        total_expense = sum(
            b.get("amount", 0) or 0
            for b in bills
            if b.get("currency", "CNY") == "CNY"
        )

        stats = {
            "recordings_count": len(recordings),
            "total_duration_sec": round(total_duration, 1),
            "total_duration_min": round(total_duration / 60, 1),
            "utterances_count": len(utterances),
            "speakers_count": len(unique_speakers),
            "events_count": len(events),
            "todos_completed": todos_completed,
            "todos_pending": todos_pending,
            "total_expense": round(total_expense, 2),
        }

        # ------------------------------------------------------------------
        # Generate highlights
        # ------------------------------------------------------------------
        highlights = []

        # Top topics
        all_topics = []
        for r in recordings:
            topics = r.get("topics", []) or []
            if isinstance(topics, list):
                all_topics.extend(topics)
        if all_topics:
            top_topics = Counter(all_topics).most_common(3)
            highlights.append(f"本周主要话题: {', '.join(t[0] for t in top_topics)}")

        # Key events
        if events:
            evt_titles = [e.get("title", "") for e in events[:3]]
            highlights.append(f"重要事件: {', '.join(evt_titles)}")

        # Recording count
        if recordings:
            highlights.append(
                f"共记录 {len(recordings)} 段语音，总计 {stats['total_duration_min']:.0f} 分钟"
            )

        # Todos
        if todos:
            completion_pct = 100 * todos_completed // len(todos) if todos else 0
            highlights.append(f"待办完成率: {todos_completed}/{len(todos)} ({completion_pct}%)")

        # ------------------------------------------------------------------
        # Emotion analysis
        # ------------------------------------------------------------------
        emotion_counter = Counter(emotions_raw.values()) if emotions_raw else Counter()
        emotions = dict(emotion_counter)

        # ------------------------------------------------------------------
        # Chart data
        # ------------------------------------------------------------------

        # Daily minutes
        daily_minutes: Dict[str, float] = {}
        for r in recordings:
            day = r.get("created_at")
            if day:
                if hasattr(day, "isoformat"):
                    day = day.isoformat()[:10]
                else:
                    day = str(day)[:10]
            else:
                day = "unknown"
            daily_minutes[day] = daily_minutes.get(day, 0) + (r.get("duration_sec", 0) or 0) / 60

        daily_minutes_list = [
            {"date": d, "minutes": round(m, 1)}
            for d, m in sorted(daily_minutes.items())
        ]

        # Emotion distribution
        emotion_distribution = [
            {"emotion": e, "count": c}
            for e, c in emotion_counter.most_common()
        ]

        # Category spending
        category_spending: Dict[str, float] = {}
        for b in bills:
            cat = b.get("category", "\u5176\u4ed6")
            category_spending[cat] = category_spending.get(cat, 0) + (b.get("amount", 0) or 0)

        category_spending_list = [
            {"category": c, "amount": round(a, 2)}
            for c, a in sorted(category_spending.items(), key=lambda x: -x[1])
        ]

        chart_data = {
            "daily_minutes": daily_minutes_list,
            "emotion_distribution": emotion_distribution,
            "category_spending": category_spending_list,
        }

        # ------------------------------------------------------------------
        # AI-generated summary
        # ------------------------------------------------------------------
        try:
            summary_text_lines = [
                f"\u672c\u5468\u7edf\u8ba1: {stats['recordings_count']}\u6bb5\u5f55\u97f3, "
                f"{stats['total_duration_min']:.0f}\u5206\u949f, "
                f"{stats['utterances_count']}\u6761\u5bf9\u8bdd, "
                f"{stats['events_count']}\u4e2a\u4e8b\u4ef6, "
                f"\u5f85\u529e\u5b8c\u6210{stats['todos_completed']}/"
                f"{stats['todos_completed'] + stats['todos_pending']}, "
                f"\u652f\u51fa{stats['total_expense']:.0f}\u5143",
            ]
            if highlights:
                summary_text_lines.append("\u4eae\u70b9: " + "; ".join(highlights[:3]))

            messages = [
                {"role": "system", "content": WEEKLY_REPORT_PROMPT},
                {"role": "user", "content": "\n".join(summary_text_lines)},
            ]
            summary = await _chat_completion(messages, temperature=0.6, max_tokens=300)
        except Exception as llm_exc:
            logger.warning("LLM weekly summary generation failed: %s", llm_exc)
            summary = "\u672c\u5468\u6570\u636e\u5df2\u6c47\u603b\uff0c\u8be6\u89c1\u5404\u9879\u7edf\u8ba1\u3002"

        logger.info(
            "Weekly report generated for %s: %d recordings, %d utterances",
            user_id, len(recordings), len(utterances),
        )

        return {
            "stats": stats,
            "highlights": highlights,
            "emotions": emotions,
            "chart_data": chart_data,
            "summary": summary,
        }

    except Exception as exc:
        logger.error("Weekly report generation failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Weekly report generation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

async def generate_daily_summary(
    user_id: str,
) -> Dict[str, Any]:
    """
    Generate a daily summary for the user (today's data).

    Uses asyncpg for all database queries.

    Args:
        user_id: The user to generate the summary for.

    Returns:
        Dict containing daily statistics and AI-generated report.

    Raises:
        RuntimeError: If data fetching fails.
    """
    logger.info("Generating daily summary for user: %s", user_id)

    try:
        from app.db import db

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

        # ------------------------------------------------------------------
        # Fetch today's recordings
        # ------------------------------------------------------------------
        rec_rows = await db.fetch(
            """
            SELECT id, duration_sec, summary, created_at
            FROM recordings
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            ORDER BY created_at DESC
            """,
            user_id, today_start, today_end,
        )
        recordings = [dict(r) for r in rec_rows]

        # ------------------------------------------------------------------
        # Fetch utterances
        # ------------------------------------------------------------------
        recording_ids = [r["id"] for r in recordings]
        utterances = []
        if recording_ids:
            utt_rows = await db.fetch(
                """
                SELECT id, speaker, text, created_at
                FROM utterances
                WHERE recording_id = ANY($1)
                ORDER BY created_at DESC
                """,
                recording_ids,
            )
            utterances = [dict(r) for r in utt_rows]

        # Count unique speakers
        unique_speakers = set()
        for u in utterances:
            spk = u.get("speaker")
            if spk:
                unique_speakers.add(spk)

        # Total duration
        total_duration = sum(r.get("duration_sec", 0) or 0 for r in recordings)

        # ------------------------------------------------------------------
        # Fetch today's events
        # ------------------------------------------------------------------
        evt_rows = await db.fetch(
            """
            SELECT id, title, event_type
            FROM events
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            ORDER BY event_date
            """,
            user_id, today_start, today_end,
        )
        events = [dict(r) for r in evt_rows]

        # ------------------------------------------------------------------
        # Fetch today's todos
        # ------------------------------------------------------------------
        todo_rows = await db.fetch(
            """
            SELECT id, title, status, source
            FROM todos
            WHERE user_id = $1 AND created_at >= $2 AND created_at < $3
            """,
            user_id, today_start, today_end,
        )
        todos = [dict(r) for r in todo_rows]

        # ------------------------------------------------------------------
        # Emotion keywords from utterances
        # ------------------------------------------------------------------
        emotion_keywords = []
        emotion_set = set()
        for u in utterances:
            emo = u.get("emotion")
            if emo:
                emotion_set.add(str(emo))
        emotion_keywords = sorted(emotion_set)

        # Build today_data for LLM daily report
        today_data = {
            "utterances": utterances,
            "todos_completed": sum(1 for t in todos if t.get("status") == "done"),
            "todos_pending": [t for t in todos if t.get("status") == "pending"],
            "events": events,
            "emotions": emotion_keywords,
            "total_chat_duration": total_duration / 60,
        }

        # Generate AI daily report
        try:
            daily_report = await generate_daily_report(user_id, today_data)
        except Exception as llm_exc:
            logger.warning("Daily report generation failed: %s", llm_exc)
            daily_report = (
                f"\u4eca\u65e5\u8bb0\u5f55\u4e86 {len(recordings)} \u6bb5\u8bed\u97f3\uff0c"
                f"\u5171 {total_duration / 60:.0f} \u5206\u949f\u3002"
            )

        result = {
            "speakers_count": len(unique_speakers),
            "total_duration": round(total_duration, 1),
            "utterances_count": len(utterances),
            "recording_count": len(recordings),
            "new_todos": todos,
            "events": events,
            "emotion_keywords": emotion_keywords,
            "daily_report": daily_report,
        }

        logger.info(
            "Daily summary generated for %s: %d recordings, %d utterances, %d speakers",
            user_id, len(recordings), len(utterances), len(unique_speakers),
        )

        return result

    except Exception as exc:
        logger.error("Daily summary generation failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Daily summary generation failed: {exc}") from exc
