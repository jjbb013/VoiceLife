# -*- coding: utf-8 -*-
"""
Calendar Event Extraction Service

Extracts time-related events from natural language text using LLM NER.
Identifies dates, times, event titles, and event types.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any

from app.services.llm_service import _chat_completion_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for calendar event extraction
# ---------------------------------------------------------------------------

CALENDAR_EXTRACTION_PROMPT = """你是一个专业的时间信息提取助手。请从以下文本中提取所有事件和时间安排。

要求：
1. 提取每个事件的标题、日期时间、事件类型
2. 日期时间尽量使用ISO 8601格式（如 2024-06-15T14:30:00），如果不能确定具体日期，使用相对描述（如"明天下午3点"）
3. 事件类型包括：meeting(会议), deadline(截止日期), reminder(提醒), activity(活动), other(其他)
4. 只提取与时间安排相关的内容，不要编造不存在的信息
5. 如果文本中没有明确的时间信息，返回空数组

请严格按JSON格式输出，不要添加任何额外说明：
{
  "events": [
    {
      "title": "事件标题",
      "event_date": "日期时间ISO格式或相对描述",
      "event_type": "事件类型"
    }
  ]
}"""


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

async def extract_calendar_events(text: str) -> List[Dict[str, Any]]:
    """
    Extract calendar events and time-related information from text.

    Uses LLM-based NER to identify event titles, dates, times, and types
    from natural language descriptions.

    Args:
        text: Input text to analyze (e.g., conversation transcript).

    Returns:
        List of event dicts, each containing:
            - title (str): Event title/name.
            - event_date (str): ISO 8601 datetime or relative description.
            - event_type (str): One of meeting/deadline/reminder/activity/other.

    Raises:
        RuntimeError: If LLM extraction fails.

    Example:
        >>> events = await extract_calendar_events(
        ...     "明天下午三点开项目评审会，周五之前要提交报告"
        ... )
        >>> print(events)
        [
            {"title": "项目评审会", "event_date": "明天下午3点", "event_type": "meeting"},
            {"title": "提交报告", "event_date": "周五之前", "event_type": "deadline"},
        ]
    """
    if not text or not text.strip():
        return []

    logger.info("Extracting calendar events from text (%d chars)", len(text))

    try:
        messages = [
            {"role": "system", "content": CALENDAR_EXTRACTION_PROMPT},
            {"role": "user", "content": f"请从以下文本中提取事件和时间安排:\n\n{text}"},
        ]

        result = await _chat_completion_json(messages, temperature=0.1)

        events = result.get("events", [])

        # Validate and clean results
        cleaned = []
        for evt in events:
            title = evt.get("title", "").strip()
            if not title:
                continue

            event_type = evt.get("event_type", "other")
            valid_types = {"meeting", "deadline", "reminder", "activity", "other"}
            if event_type not in valid_types:
                event_type = "other"

            cleaned.append({
                "title": title,
                "event_date": evt.get("event_date"),
                "event_type": event_type,
            })

        logger.info("Extracted %d calendar events", len(cleaned))
        return cleaned

    except Exception as exc:
        logger.error("Calendar event extraction failed: %s", exc, exc_info=True)
        # Return empty list on failure — don't break downstream processing
        return []


async def extract_calendar_events_from_utterances(
    utterances: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract calendar events from a list of utterances.

    Concatenates all utterance texts and performs extraction.

    Args:
        utterances: List of utterance dicts with "text" field.

    Returns:
        List of extracted event dicts.
    """
    full_text = "\n".join([
        f"{u.get('speaker', '未知')}: {u.get('text', '')}"
        for u in utterances
    ])
    return await extract_calendar_events(full_text)
