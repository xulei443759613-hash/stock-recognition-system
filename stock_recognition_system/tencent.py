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


def to_tencent_symbol(stock_code: str) -> str:
    return f"sh{stock_code}" if stock_code.startswith(("6", "9")) else f"sz{stock_code}"


def _calc_change_pct(close_prices: list[float]) -> float | None:
    if len(close_prices) < 2 or close_prices[-2] <= 0:
        return None
    return round((close_prices[-1] - close_prices[-2]) / close_prices[-2] * 100, 2)


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
