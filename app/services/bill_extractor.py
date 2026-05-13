# -*- coding: utf-8 -*-
"""
Bill / Financial Information Extraction Service

Extracts monetary amounts, currencies, categories, and context
from natural language text using LLM NER.
"""

from __future__ import annotations

import logging
import re
from typing import List, Dict, Any, Optional

from app.services.llm_service import _chat_completion_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for bill extraction
# ---------------------------------------------------------------------------

BILL_EXTRACTION_PROMPT = """你是一个专业的财务信息提取助手。请从以下文本中提取所有与金钱、消费、账单相关的信息。

提取要求：
1. 金额（amount）：提取数字，转换为标准数值（如 1500、89.50、20000）
2. 币种（currency）：识别币种代码（CNY人民币、USD美元、EUR欧元、GBP英镑、JPY日元等），默认为 CNY
3. 类别（category）：消费/账单类别，如 餐饮、交通、购物、娱乐、住房、医疗、教育、工资、转账、投资、其他
4. 上下文（context）：简要描述这笔消费/收入的上下文（1-2句话）

只提取文本中明确提到的金额，不要编造。如果文本中没有财务信息，返回空数组。

请严格按JSON格式输出，不要添加任何额外说明：
{
  "bills": [
    {
      "amount": 1500.00,
      "currency": "CNY",
      "category": "餐饮",
      "context": "晚上和朋友在海底捞聚餐"
    }
  ]
}"""


# ---------------------------------------------------------------------------
# Regex-based fallback extraction patterns
# ---------------------------------------------------------------------------

# Chinese numerals mapping
_CN_NUMBERS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000, "万": 10000, "亿": 100000000,
}

# Regex for Chinese monetary expressions
_CURRENCY_PATTERNS = [
    # 1500元 / 1,500元 / 1500.50元
    r"(\d{1,3}(?:,\d{3})*\.?\d*)\s*[元块](?:人民币)?",
    # ¥1500 / ¥ 1,500
    r"[¥￥]\s*(\d{1,3}(?:,\d{3})*\.?\d*)",
    # 1500 USD / $1500
    r"[\$]\s*(\d{1,3}(?:,\d{3})*\.?\d*)\s*(?:USD)?",
    # 一百五十元 / 两千块
    r"([一二两三四五六七八九十百千万亿]+)\s*[元块]",
    # 花了1500 / 花费1500元
    r"(?:花|花费|消费|支出|用了|付了|转账|转给).*?(\d{1,3}(?:,\d{3})*\.?\d*)\s*[元块]?(?:人民币)?",
    # 收入/收到 + 金额
    r"(?:收入|收到|到账|工资).*?(\d{1,3}(?:,\d{3})*\.?\d*)\s*[元块]?(?:人民币)?",
]

_CURRENCY_MAP = {
    "元": "CNY", "块": "CNY", "人民币": "CNY",
    "美元": "USD", "$": "USD", "USD": "USD",
    "欧元": "EUR", "EUR": "EUR", "eur": "EUR",
    "英镑": "GBP", "GBP": "GBP",
    "日元": "JPY", "JPY": "JPY", "円": "JPY",
    "港币": "HKD", "港元": "HKD", "HKD": "HKD",
    "台币": "TWD", "新台币": "TWD", "TWD": "TWD",
}

_CATEGORY_KEYWORDS = {
    "餐饮": ["吃", "饭", "餐厅", "火锅", "烧烤", "外卖", "咖啡", "奶茶", "海底捞", "肯德基", "麦当劳"],
    "交通": ["打车", "滴滴", "地铁", "公交", "高铁", "机票", "加油", "停车费", "高速费"],
    "购物": ["买", "购物", "淘宝", "京东", "拼多多", "衣服", "鞋", "包", "超市"],
    "娱乐": ["电影", "KTV", "游戏", "演唱会", "旅游", "旅行", "酒吧"],
    "住房": ["房租", "房租", "水电", "物业", "宽带", "装修", "房贷"],
    "医疗": ["医院", "看病", "药", "体检", "挂号", "医保"],
    "教育": ["学费", "培训", "课程", "书本", "考试"],
    "工资": ["工资", "薪水", "薪资", "收入", "发薪"],
    "转账": ["转账", "转给", "汇款", "红包"],
    "投资": ["股票", "基金", "理财", "投资"],
}


def _parse_chinese_number(cn_str: str) -> Optional[float]:
    """
    Parse a Chinese numeral string to a float.

    Args:
        cn_str: Chinese numeral string like "一百五十", "两千".

    Returns:
        Parsed number or None.
    """
    if not cn_str:
        return None

    # Try simple Arabic numeral first
    try:
        return float(cn_str.replace(",", ""))
    except ValueError:
        pass

    total = 0
    current = 0
    for char in cn_str:
        if char in _CN_NUMBERS:
            val = _CN_NUMBERS[char]
            if val >= 10:
                if current == 0:
                    current = 1
                total += current * val
                current = 0
            else:
                current = current * 10 + val if current else val
        else:
            return None

    return float(total + current)


def _detect_currency(text: str) -> str:
    """Detect currency from surrounding text context."""
    for keyword, code in _CURRENCY_MAP.items():
        if keyword in text:
            return code
    return "CNY"


def _detect_category(text: str) -> str:
    """Detect spending category from text context."""
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "其他"


# ---------------------------------------------------------------------------
# Main extraction functions
# ---------------------------------------------------------------------------

async def extract_bills(text: str) -> List[Dict[str, Any]]:
    """
    Extract bill/financial information from text.

    Uses LLM-based extraction with regex fallback for robustness.
    Identifies monetary amounts, currencies, categories, and context.

    Args:
        text: Input text to analyze (e.g., conversation transcript).

    Returns:
        List of bill dicts, each containing:
            - amount (float): Monetary amount.
            - currency (str): Currency code (CNY/USD/EUR/etc.).
            - category (str): Spending category.
            - context (str): Brief description of the transaction.

    Raises:
        RuntimeError: If extraction completely fails (returns empty list on recoverable errors).

    Example:
        >>> bills = await extract_bills(
        ...     "今天中午在海底捞花了350块，晚上打车回家用了45元"
        ... )
        >>> print(bills)
        [
            {"amount": 350, "currency": "CNY", "category": "餐饮", "context": "在海底捞聚餐"},
            {"amount": 45, "currency": "CNY", "category": "交通", "context": "打车回家"},
        ]
    """
    if not text or not text.strip():
        return []

    logger.info("Extracting bills from text (%d chars)", len(text))

    # Try LLM-based extraction first
    llm_results = []
    try:
        messages = [
            {"role": "system", "content": BILL_EXTRACTION_PROMPT},
            {"role": "user", "content": f"请从以下文本中提取账单信息:\n\n{text}"},
        ]

        result = await _chat_completion_json(messages, temperature=0.1)
        raw_bills = result.get("bills", [])

        for bill in raw_bills:
            amount = bill.get("amount")
            if amount is None:
                continue

            # Normalize amount
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                continue

            if amount <= 0:
                continue

            llm_results.append({
                "amount": amount,
                "currency": bill.get("currency", "CNY").upper() or "CNY",
                "category": bill.get("category", "其他"),
                "context": bill.get("context", ""),
            })

        logger.info("LLM extracted %d bills", len(llm_results))

    except Exception as exc:
        logger.warning("LLM bill extraction failed, using fallback: %s", exc)

    # If LLM returns results, use them; otherwise fall back to regex
    if llm_results:
        return llm_results

    return _extract_bills_regex(text)


def _extract_bills_regex(text: str) -> List[Dict[str, Any]]:
    """
    Fallback regex-based bill extraction.

    Args:
        text: Input text.

    Returns:
        List of bill dicts.
    """
    logger.info("Using regex fallback for bill extraction")

    bills = []
    seen = set()

    for pattern in _CURRENCY_PATTERNS:
        for match in re.finditer(pattern, text):
            matched_text = match.group(0)
            amount_str = match.group(1) if match.lastindex and match.lastindex >= 1 else matched_text

            # Parse amount
            amount = _parse_chinese_number(amount_str)
            if amount is None:
                try:
                    amount = float(amount_str.replace(",", ""))
                except (ValueError, TypeError):
                    continue

            if amount <= 0:
                continue

            # Deduplicate
            key = (round(amount, 2), matched_text)
            if key in seen:
                continue
            seen.add(key)

            # Detect currency and category from surrounding context
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end]

            currency = _detect_currency(matched_text)
            category = _detect_category(context)

            bills.append({
                "amount": amount,
                "currency": currency,
                "category": category,
                "context": context.strip(),
            })

    logger.info("Regex fallback extracted %d bills", len(bills))
    return bills


async def extract_bills_from_utterances(
    utterances: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract bills from a list of utterances.

    Args:
        utterances: List of utterance dicts with "text" field.

    Returns:
        List of extracted bill dicts.
    """
    full_text = "\n".join([
        f"{u.get('speaker', '未知')}: {u.get('text', '')}"
        for u in utterances
    ])
    return await extract_bills(full_text)
