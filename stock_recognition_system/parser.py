from __future__ import annotations

import re

from .models import GroupMessage, ParsedSignal


def _first(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.S)
    return match.group(1).strip() if match else None


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip().rstrip("元")
    try:
        return float(value)
    except ValueError:
        return None


def _split_logic(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[+＋,，、\s]+", value)
    return [part.strip("。；;") for part in parts if part.strip("。；;")]


def _first_price(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        value = _first(pattern, text)
        price = _to_float(value)
        if price is not None:
            return price
    return None


def _first_range(patterns: list[str], text: str) -> tuple[float | None, float | None]:
    for pattern in patterns:
        match = re.search(pattern, text, re.S)
        if match:
            return _to_float(match.group(1)), _to_float(match.group(2))
    return None, None


def parse_group_message(message: GroupMessage) -> ParsedSignal:
    text = message.raw_text
    stock_match = re.search(r"【?\s*([\u4e00-\u9fa5A-Za-z*ST]+)\s+([0-9]{6})\s*】?", text)
    if not stock_match:
        stock_match = re.search(r"([0-9]{6})\s+([\u4e00-\u9fa5A-Za-z*ST]+)", text)

    entry_low, entry_high = _first_range(
        [
            r"(?:入场|买入|建仓|低吸)(?:参考|区间|价位)?[：:]\s*([0-9.]+)\s*(?:~|\-|—|至|到)\s*([0-9.]+)",
            r"(?:入场|买入|建仓|低吸)(?:参考|区间|价位)?[：:]\s*([0-9.]+)\s*[元块]?\s*[/-]\s*([0-9.]+)",
        ],
        text,
    )
    logic = _first(r"(?:参考逻辑|推荐逻辑|逻辑|理由)[：:]\s*(.+?)(?:\n\n|【|$)", text)

    if stock_match and stock_match.group(1).isdigit():
        stock_code = stock_match.group(1)
        stock_name = stock_match.group(2)
    else:
        stock_name = stock_match.group(1) if stock_match else None
        stock_code = stock_match.group(2) if stock_match else None

    return ParsedSignal(
        stock_name=stock_name,
        stock_code=stock_code,
        entry_low=entry_low,
        entry_high=entry_high,
        target_price=_first_price(
            [
                r"(?:目标|止盈)(?:参考|价|位)?[：:]\s*([0-9.]+)",
                r"(?:看至|看到|看)\s*([0-9.]+)",
            ],
            text,
        ),
        stop_loss=_first_price(
            [
                r"(?:止损|风控)(?:参考|价|位)?[：:]\s*([0-9.]+)",
                r"(?:跌破|破位)\s*([0-9.]+)",
            ],
            text,
        ),
        claimed_logic=_split_logic(logic),
        adviser_text=_first(r"(证书编号.+)", text),
    )
