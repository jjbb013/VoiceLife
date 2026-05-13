# -*- coding: utf-8 -*-
"""
LLM Service — Kimi API Client

Encapsulates Moonshot AI (Kimi) API via OpenAI-compatible client.
Provides conversation analysis, chat with memory, meeting summary,
and daily report generation.

Environment variables:
    KIMI_API_KEY: Moonshot API key (required).
    KIMI_BASE_URL: API base URL (default: https://api.moonshot.cn/v1).
    KIMI_MODEL: Model name (default: moonshot-v1-128k).
    KIMI_TIMEOUT: Request timeout in seconds (default: 120).
"""

from __future__ import annotations

import os
import json
import logging
from typing import List, Dict, Any, Optional

import openai

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-128k")
KIMI_TIMEOUT = float(os.getenv("KIMI_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# OpenAI-compatible async client
# ---------------------------------------------------------------------------
_client: Optional[openai.AsyncOpenAI] = None


def get_client() -> openai.AsyncOpenAI:
    """
    Get or create the global async OpenAI client for Kimi API.

    Returns:
        Initialized AsyncOpenAI client.

    Raises:
        RuntimeError: If KIMI_API_KEY is not configured.
    """
    global _client

    if _client is not None:
        return _client

    if not KIMI_API_KEY:
        raise RuntimeError(
            "KIMI_API_KEY environment variable is not set. "
            "Please configure it in your .env file."
        )

    _client = openai.AsyncOpenAI(
        api_key=KIMI_API_KEY,
        base_url=KIMI_BASE_URL,
        timeout=KIMI_TIMEOUT,
        max_retries=3,
    )
    logger.info("Kimi API client initialized: %s", KIMI_BASE_URL)
    return _client


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

async def _chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    response_format: Optional[Dict[str, str]] = None,
) -> str:
    """
    Send a chat completion request to the Kimi API.

    Args:
        messages: List of message dicts with "role" and "content".
        model: Override model name.
        temperature: Sampling temperature (0.0 - 1.0).
        max_tokens: Maximum tokens to generate.
        response_format: Optional response format specification.

    Returns:
        Generated text content from the LLM.

    Raises:
        RuntimeError: If the API call fails after retries.
    """
    client = get_client()
    model_name = model or KIMI_MODEL

    try:
        logger.debug(
            "Sending chat completion: model=%s, messages=%d, temp=%.2f",
            model_name, len(messages), temperature,
        )

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content
        logger.debug(
            "Chat completion received: %d chars, prompt_tokens=%d, completion_tokens=%d",
            len(content),
            response.usage.prompt_tokens if response.usage else 0,
            response.usage.completion_tokens if response.usage else 0,
        )
        return content.strip()

    except openai.APITimeoutError as exc:
        logger.error("Kimi API timeout: %s", exc)
        raise RuntimeError(f"Kimi API timeout after {KIMI_TIMEOUT}s") from exc

    except openai.APIError as exc:
        logger.error("Kimi API error: %s", exc)
        raise RuntimeError(f"Kimi API error: {exc}") from exc

    except Exception as exc:
        logger.error("Unexpected error calling Kimi API: %s", exc, exc_info=True)
        raise RuntimeError(f"LLM request failed: {exc}") from exc


async def _chat_completion_json(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """
    Send a chat completion request and parse the result as JSON.

    Args:
        messages: List of message dicts.
        model: Override model name.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.

    Returns:
        Parsed JSON dict.

    Raises:
        RuntimeError: If response cannot be parsed as JSON.
    """
    content = await _chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Kimi may wrap JSON in markdown code blocks — strip them
    cleaned = content
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM response as JSON: %s\nRaw: %s", exc, content)
        # Return a minimal fallback structure
        return {"raw_response": content, "parse_error": str(exc)}


# ---------------------------------------------------------------------------
# High-level business functions
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """你是一个专业的语音助手分析专家。请分析用户提供的对话内容，提取关键信息。
请严格按JSON格式输出，不要添加任何额外说明。JSON字段如下：
- summary: 100字以内的中文摘要
- topics: 话题标签数组（每个标签2-6个字）
- events: 事件数组，每个事件包含 title(标题), event_date(日期，ISO格式或null), event_type(类型: meeting/deadline/reminder/activity/other)
- todos: 待办事项数组，每个包含 title(标题), due_date(截止日期ISO格式或null), owner(负责人或null)
- bills: 账单数组，每个包含 amount(金额数字), currency(币种CNY/USD等), category(类别), context(上下文描述)
- emotions: 情绪分析对象，key为说话人标识，value为情绪标签(happy/sad/angry/anxious/calm/excited/tired/neutral)
"""


async def analyze_conversation(
    text: str,
    utterances: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    调用 Kimi 对对话进行深度分析。

    Args:
        text: 完整拼接的对话文本。
        utterances: 说话人分段列表，每个元素包含 speaker, text, start, end。

    Returns:
        JSON 对象，包含以下字段：
            - summary (str): 100字以内中文摘要
            - topics (List[str]): 话题标签数组
            - events (List[Dict]): 事件数组 [{title, event_date, event_type}]
            - todos (List[Dict]): 待办数组 [{title, due_date, owner}]
            - bills (List[Dict]): 账单数组 [{amount, currency, category, context}]
            - emotions (Dict[str, str]): 情绪分析 {speaker: emotion}

    Raises:
        RuntimeError: If API call or JSON parsing fails.

    Example:
        >>> result = await analyze_conversation("Alice: 明天下午三点开会...", [...])
        >>> print(result["summary"])
        "讨论了明天的会议安排和项目进度"
    """
    logger.info("Analyzing conversation: %d utterances", len(utterances))

    # Build structured utterance summary for the prompt
    utterance_text = "\n".join([
        f"[{u.get('start', '?')}s] {u.get('speaker', '未知')}: {u.get('text', '')}"
        for u in utterances[:100]  # Limit to first 100 utterances
    ])

    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": f"完整文本:\n{text}\n\n分段记录:\n{utterance_text}\n\n请分析以上对话内容，按要求的JSON格式输出分析结果。"},
    ]

    result = await _chat_completion_json(messages, temperature=0.2)

    # Ensure all expected keys exist
    defaults = {
        "summary": text[:100] if text else "无内容",
        "topics": [],
        "events": [],
        "todos": [],
        "bills": [],
        "emotions": {},
    }
    for key, default_val in defaults.items():
        if key not in result:
            result[key] = default_val

    logger.info(
        "Conversation analysis completed: topics=%d, events=%d, todos=%d, bills=%d",
        len(result["topics"]),
        len(result["events"]),
        len(result["todos"]),
        len(result["bills"]),
    )
    return result


CHAT_SYSTEM_PROMPT = """你是 AILife，一个AI随身语音助手。你的角色是用户的智能伙伴，帮助用户记录生活、
管理待办、回忆往事、提供建议。你性格温暖、机智、简洁。回答要简短有力，适合语音播报。
当用户提到人名、事件、待办时，请自然地回应并记住这些信息。当前时间：{now}。"""


async def chat_with_memory(
    user_id: str,
    message: str,
    context: Dict[str, Any],
) -> str:
    """
    AI 聊天，注入长期记忆上下文。

    Args:
        user_id: 用户唯一标识。
        message: 用户当前输入消息。
        context: 上下文信息，可能包含：
            - recent_utterances: 最近对话记录
            - memories: 相关长期记忆
            - todos: 当前待办列表
            - user_profile: 用户画像
            - now: 当前时间字符串

    Returns:
        AI 回复文本（简洁，适合语音播报）。

    Example:
        >>> reply = await chat_with_memory("user_001", "我明天有什么安排？", {...})
        >>> print(reply)
        "明天下午3点有一个项目评审会议。"
    """
    from datetime import datetime

    now = context.get("now", datetime.now().isoformat())

    # Build system prompt with context
    system_content = CHAT_SYSTEM_PROMPT.format(now=now)

    # Inject relevant memories
    memories = context.get("memories", [])
    if memories:
        memory_text = "\n".join([f"- {m}" for m in memories[:10]])
        system_content += f"\n\n相关记忆:\n{memory_text}"

    # Inject recent todos
    todos = context.get("todos", [])
    if todos:
        todo_text = "\n".join([f"- {t.get('title', '未知')}" for t in todos[:10]])
        system_content += f"\n\n当前待办:\n{todo_text}"

    messages = [
        {"role": "system", "content": system_content},
    ]

    # Add recent conversation history
    recent = context.get("recent_utterances", [])
    for utterance in recent[-10:]:  # Last 10 turns
        role = "user" if utterance.get("is_user", True) else "assistant"
        messages.append({
            "role": role,
            "content": utterance.get("text", ""),
        })

    # Add current message
    messages.append({"role": "user", "content": message})

    return await _chat_completion(
        messages=messages,
        temperature=0.7,
        max_tokens=512,
    )


MEETING_SUMMARY_PROMPT = """你是一个专业的会议纪要助手。请根据以下会议对话记录，生成结构化的会议纪要。
请严格按JSON格式输出：
{
  "title": "会议标题",
  "decisions": ["决策1", "决策2"],
  "action_items": [{"task": "任务描述", "owner": "负责人", "deadline": "截止日期或null"}],
  "questions": ["待确认问题1", "待确认问题2"],
  "participants": ["参与者1", "参与者2"]
}"""


async def generate_meeting_summary(
    utterances: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    生成会议纪要。

    Args:
        utterances: 会议对话分段列表，每个元素包含 speaker, text, start, end。

    Returns:
        JSON 对象，包含：
            - title (str): 会议标题
            - decisions (List[str]): 决策列表
            - action_items (List[Dict]): 行动项 [{task, owner, deadline}]
            - questions (List[str]): 待确认问题列表
            - participants (List[str]): 参与者列表

    Example:
        >>> summary = await generate_meeting_summary(utterances)
        >>> print(summary["decisions"])
        ["确定使用React作为前端框架", "下周一开始 sprint 3"]
    """
    logger.info("Generating meeting summary from %d utterances", len(utterances))

    dialogue_text = "\n".join([
        f"{u.get('speaker', '未知')} ({u.get('start', 0):.0f}s): {u.get('text', '')}"
        for u in utterances
    ])

    messages = [
        {"role": "system", "content": MEETING_SUMMARY_PROMPT},
        {"role": "user", "content": f"请为以下会议生成纪要:\n\n{dialogue_text}"},
    ]

    result = await _chat_completion_json(messages, temperature=0.2)

    # Ensure defaults
    defaults = {
        "title": "会议",
        "decisions": [],
        "action_items": [],
        "questions": [],
        "participants": [],
    }
    for key, default_val in defaults.items():
        if key not in result:
            result[key] = default_val

    logger.info(
        "Meeting summary generated: %d decisions, %d action items",
        len(result["decisions"]), len(result["action_items"]),
    )
    return result


DAILY_REPORT_PROMPT = """你是一个贴心的生活助手。请根据用户今天的活动记录，生成一段200字以内的睡前语音日报。
要求：
1. 语气温暖亲切，像朋友在耳边轻声讲述
2. 回顾今天的亮点和重要事件
3. 提及未完成的待办事项（如有）
4. 给予鼓励和温暖的晚安祝福
5. 适合语音播报，句子简短流畅
请直接输出纯文本，不要加JSON格式或其他标记。"""


async def generate_daily_report(
    user_id: str,
    today_data: Dict[str, Any],
) -> str:
    """
    生成睡前语音日报文本（200字以内）。

    Args:
        user_id: 用户唯一标识。
        today_data: 今日数据，包含：
            - utterances: 今日对话记录
            - todos_completed: 已完成待办数
            - todos_pending: 未完成待办列表
            - events: 今日事件列表
            - emotions: 今日情绪关键词
            - total_chat_duration: 总聊天时长（分钟）

    Returns:
        日报文本字符串（温暖亲切，适合语音播报）。

    Example:
        >>> report = await generate_daily_report("user_001", {...})
        >>> print(report)
        "今天真是充实的一天呢！上午你完成了项目提案的撰写，下午和团队讨论了下周的计划...
         还有2件事记得明天处理哦。晚安，好梦！"
    """
    logger.info("Generating daily report for user: %s", user_id)

    # Build today's activity summary
    lines = []

    # Events
    events = today_data.get("events", [])
    if events:
        event_titles = [e.get("title", "某事") for e in events[:5]]
        lines.append(f"今日事件: {', '.join(event_titles)}")

    # Todos
    completed = today_data.get("todos_completed", 0)
    pending = today_data.get("todos_pending", [])
    lines.append(f"完成待办: {completed}项")
    if pending:
        pending_titles = [t.get("title", "未知") for t in pending[:5]]
        lines.append(f"待处理: {', '.join(pending_titles)}")

    # Emotions
    emotions = today_data.get("emotions", [])
    if emotions:
        lines.append(f"情绪关键词: {', '.join(emotions[:5])}")

    # Duration
    duration = today_data.get("total_chat_duration", 0)
    if duration:
        lines.append(f"语音交互: {duration:.0f}分钟")

    activity_text = "\n".join(lines) if lines else "今日暂无记录"

    messages = [
        {"role": "system", "content": DAILY_REPORT_PROMPT},
        {"role": "user", "content": f"用户今日数据:\n{activity_text}\n\n请生成睡前日报。"},
    ]

    report = await _chat_completion(
        messages=messages,
        temperature=0.8,
        max_tokens=300,
    )

    logger.info(
        "Daily report generated for %s: %d chars", user_id, len(report),
    )
    return report


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def health_check() -> bool:
    """
    Check if the Kimi API is accessible.

    Returns:
        True if API responds, False otherwise.
    """
    try:
        client = get_client()
        # Try a minimal request
        await client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return True
    except Exception as exc:
        logger.warning("Kimi API health check failed: %s", exc)
        return False
