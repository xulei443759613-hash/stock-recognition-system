from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from .models import InformationSource, MarketEvidence, SourceTier


@dataclass
class TencentDailyDataProvider:
    """Fetch recent daily closes from Tencent's public quote endpoint."""

    close_count: int = 20

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        symbol = to_tencent_symbol(stock_code)
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{max(1, self.close_count)},qfq"
        request = Request(
            url,
            headers={
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://gu.qq.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        parsed = parse_tencent_daily_payload(payload, symbol)
        source = InformationSource("腾讯行情", SourceTier.LICENSED_DATA_VENDOR, url="https://gu.qq.com")
        if not parsed.close_prices:
            return MarketEvidence(
                data_warnings=[f"Tencent 未返回 {stock_code} 日线数据"],
                information_sources=[source],
                raw={"stock_code": stock_code, "url": url, "payload": payload},
            )

        return MarketEvidence(
            current_price=parsed.current_price,
            change_pct=parsed.change_pct,
            turnover_rate=parsed.turnover_rate,
            close_prices=parsed.close_prices,
            is_limit_up=parsed.change_pct is not None and parsed.change_pct >= 9.8,
            data_warnings=["Tencent 日线数据，仅用于风控核验；真实交易前需再次确认"],
            information_sources=[source],
            raw={"stock_code": stock_code, "url": url, "latest": parsed.latest_raw},
        )


@dataclass
class TencentDailyKlines:
    close_prices: list[float]
    current_price: float | None
    change_pct: float | None
    turnover_rate: float | None
    latest_raw: list[Any] | None


@dataclass
class TencentIntradayDataProvider:
    """Fetch recent intraday minute prices from Tencent's public quote endpoint."""

    def get_evidence_at(self, stock_code: str, trade_date: str, trade_time: str) -> MarketEvidence:
        symbol = to_tencent_symbol(stock_code)
        url = f"https://web.ifzq.gtimg.cn/appstock/app/day/query?code={symbol}"
        request = Request(
            url,
            headers={
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://gu.qq.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        parsed = parse_tencent_intraday_payload(payload, symbol, trade_date, trade_time)
        source = InformationSource("腾讯分时", SourceTier.LICENSED_DATA_VENDOR, url="https://gu.qq.com")
        if parsed.price is None:
            return MarketEvidence(
                data_warnings=[f"Tencent 未返回 {stock_code} {trade_date} {trade_time} 分时价格"],
                information_sources=[source],
                raw={"stock_code": stock_code, "url": url, "payload": payload},
            )

        return MarketEvidence(
            current_price=parsed.price,
            change_pct=parsed.change_pct,
            is_limit_up=parsed.change_pct is not None and parsed.change_pct >= 9.8,
            data_warnings=[
                f"Tencent 分时价格：{parsed.trade_date} {parsed.matched_time}，用于还原消息发出时价格"
            ],
            information_sources=[source],
            raw={"stock_code": stock_code, "url": url, "matched": parsed.latest_raw},
        )


@dataclass
class TencentIntradayPrice:
    price: float | None
    trade_date: str | None
    matched_time: str | None
    latest_raw: str | None
    previous_close: float | None = None
    change_pct: float | None = None


def parse_tencent_daily_payload(payload: dict[str, Any], symbol: str) -> TencentDailyKlines:
    symbol_data = ((payload.get("data") or {}).get(symbol) or {})
    rows = symbol_data.get("qfqday") or symbol_data.get("day") or []
    close_prices: list[float] = []
    latest_raw: list[Any] | None = None

    for row in rows:
        if not isinstance(row, list) or len(row) < 3:
            continue
        close = _to_float(row[2])
        if close is None:
            continue
        close_prices.append(close)
        latest_raw = row

    quote = ((symbol_data.get("qt") or {}).get(symbol) or [])
    quote_price = _quote_float(quote, 3)
    quote_change_pct = _quote_float(quote, 32)
    quote_turnover = _quote_float(quote, 38)

    current_price = close_prices[-1] if close_prices else quote_price
    change_pct = quote_change_pct if quote_change_pct is not None else _calc_change_pct(close_prices)
    return TencentDailyKlines(close_prices, current_price, change_pct, quote_turnover, latest_raw)


def parse_tencent_intraday_payload(
    payload: dict[str, Any],
    symbol: str,
    trade_date: str,
    trade_time: str,
) -> TencentIntradayPrice:
    target_date = _normalize_trade_date(trade_date)
    target_time = _normalize_trade_time(trade_time)
    symbol_data = ((payload.get("data") or {}).get(symbol) or {})
    day_rows = _intraday_days(symbol_data)

    rows: list[str] = []
    previous_close: float | None = None
    for day in day_rows:
        if str(day.get("date", "")) == target_date:
            raw_rows = day.get("data") or []
            rows = [row for row in raw_rows if isinstance(row, str)]
            previous_close = _to_float(day.get("prec"))
            break

    matched = _match_intraday_row(rows, target_time)
    if matched is None:
        return TencentIntradayPrice(None, target_date, None, None, previous_close, None)

    parts = matched.split()
    price = _to_float(parts[1]) if len(parts) > 1 else None
    change_pct = _calc_single_change_pct(price, previous_close)
    return TencentIntradayPrice(price, target_date, _format_trade_time(parts[0]), matched, previous_close, change_pct)


def to_tencent_symbol(stock_code: str) -> str:
    return f"sh{stock_code}" if stock_code.startswith(("6", "9")) else f"sz{stock_code}"


def _calc_change_pct(close_prices: list[float]) -> float | None:
    if len(close_prices) < 2 or close_prices[-2] <= 0:
        return None
    return round((close_prices[-1] - close_prices[-2]) / close_prices[-2] * 100, 2)


def _calc_single_change_pct(price: float | None, previous_close: float | None) -> float | None:
    if price is None or previous_close is None or previous_close <= 0:
        return None
    return round((price - previous_close) / previous_close * 100, 2)


def _intraday_days(symbol_data: dict[str, Any]) -> list[dict[str, Any]]:
    data = symbol_data.get("data") or []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _match_intraday_row(rows: list[str], target_time: str) -> str | None:
    target_minutes = _time_to_minutes(target_time)
    if target_minutes is None:
        return None

    matched: str | None = None
    matched_minutes: int | None = None
    for row in rows:
        parts = row.split()
        if not parts:
            continue
        row_time = _normalize_trade_time(parts[0])
        row_minutes = _time_to_minutes(row_time)
        if row_minutes is None or row_minutes > target_minutes:
            continue
        if matched_minutes is None or row_minutes >= matched_minutes:
            matched = row
            matched_minutes = row_minutes
    return matched


def _normalize_trade_date(value: str) -> str:
    return value.strip().replace("-", "")


def _normalize_trade_time(value: str) -> str:
    normalized = value.strip().replace(":", "")
    return normalized.zfill(4)


def _format_trade_time(value: str) -> str:
    normalized = _normalize_trade_time(value)
    return f"{normalized[:2]}:{normalized[2:]}"


def _time_to_minutes(value: str) -> int | None:
    normalized = _normalize_trade_time(value)
    if len(normalized) != 4 or not normalized.isdigit():
        return None
    return int(normalized[:2]) * 60 + int(normalized[2:])


def _quote_float(values: list[Any], index: int) -> float | None:
    if len(values) <= index:
        return None
    return _to_float(values[index])


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
