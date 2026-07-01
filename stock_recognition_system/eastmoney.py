from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from .models import InformationSource, MarketEvidence, SourceTier


@dataclass
class EastMoneyDailyDataProvider:
    """Fetch recent daily closes from EastMoney public K-line API."""

    close_count: int = 20

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        secid = to_eastmoney_secid(stock_code)
        source = InformationSource("东方财富", SourceTier.LICENSED_DATA_VENDOR, url="https://quote.eastmoney.com")
        kline_url = (
            "https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            "&fields1=f1,f2,f3,f4,f5,f6"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            "&klt=101&fqt=1&end=20500101"
            f"&lmt={max(1, self.close_count)}"
        )
        warnings: list[str] = []
        try:
            payload = _fetch_json(kline_url)
            klines = (payload.get("data") or {}).get("klines") or []
            parsed = parse_daily_klines(klines)
            if parsed.close_prices:
                return MarketEvidence(
                    current_price=parsed.close_prices[-1],
                    change_pct=parsed.change_pct,
                    turnover_rate=parsed.turnover_rate,
                    close_prices=parsed.close_prices,
                    high_prices=parsed.high_prices,
                    low_prices=parsed.low_prices,
                    is_limit_up=parsed.change_pct is not None and parsed.change_pct >= 9.8,
                    data_warnings=["EastMoney 日线数据，仅用于风控核验；真实交易前需再次确认"],
                    information_sources=[source],
                    raw={"stock_code": stock_code, "url": kline_url, "latest": parsed.latest_raw},
                )
            warnings.append(f"EastMoney 未返回 {stock_code} 日线数据")
        except Exception as exc:
            warnings.append(f"EastMoney K-line API failed: {exc}")

        realtime_url = (
            "https://push2.eastmoney.com/api/qt/stock/get"
            "?ut=fa5fd1943c7b386f172d6893dbfba10b&invt=2&fltt=2"
            f"&secid={secid}"
            "&fields=f43,f57,f58,f60,f162,f168,f169,f170"
        )
        try:
            payload = _fetch_json(realtime_url)
            parsed_quote = parse_realtime_quote(payload)
            if parsed_quote.current_price is None:
                return MarketEvidence(
                    data_warnings=warnings + [f"EastMoney 未返回 {stock_code} 实时行情"],
                    information_sources=[source],
                    raw={"stock_code": stock_code, "url": realtime_url, "payload": payload},
                )
            return MarketEvidence(
                current_price=parsed_quote.current_price,
                change_pct=parsed_quote.change_pct,
                turnover_rate=parsed_quote.turnover_rate,
                is_limit_up=parsed_quote.change_pct is not None and parsed_quote.change_pct >= 9.8,
                data_warnings=warnings
                + ["EastMoney 实时行情降级：无历史收盘价序列，仅用于当前价/涨跌幅/换手率核验"],
                information_sources=[source],
                raw={"stock_code": stock_code, "url": realtime_url, "latest": parsed_quote.latest_raw},
            )
        except Exception as exc:
            return MarketEvidence(
                data_warnings=warnings + [f"EastMoney real-time API failed: {exc}"],
                information_sources=[source],
                raw={"stock_code": stock_code, "url": realtime_url},
            )


@dataclass
class EastMoneyDailyKlines:
    close_prices: list[float]
    high_prices: list[float]
    low_prices: list[float]
    change_pct: float | None
    turnover_rate: float | None
    latest_raw: str | None


@dataclass
class EastMoneyRealtimeQuote:
    current_price: float | None
    change_pct: float | None
    turnover_rate: float | None
    latest_raw: dict[str, Any]


def parse_daily_klines(klines: list[str]) -> EastMoneyDailyKlines:
    close_prices: list[float] = []
    high_prices: list[float] = []
    low_prices: list[float] = []
    latest_raw: str | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None
    for raw in klines:
        parts = raw.split(",")
        if len(parts) < 5:
            continue
        close = _to_float(parts[2])
        high = _to_float(parts[3])
        low = _to_float(parts[4])
        if close is None:
            continue
        close_prices.append(close)
        if high is not None:
            high_prices.append(high)
        if low is not None:
            low_prices.append(low)
        latest_raw = raw
        if len(parts) > 8:
            change_pct = _to_float(parts[8])
        if len(parts) > 10:
            turnover_rate = _to_float(parts[10])
    return EastMoneyDailyKlines(close_prices, high_prices, low_prices, change_pct, turnover_rate, latest_raw)


def parse_realtime_quote(payload: dict[str, Any]) -> EastMoneyRealtimeQuote:
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    return EastMoneyRealtimeQuote(
        current_price=_eastmoney_scaled(data.get("f43")),
        change_pct=_eastmoney_scaled(data.get("f170")),
        turnover_rate=_eastmoney_scaled(data.get("f168")),
        latest_raw=data,
    )


def to_eastmoney_secid(stock_code: str) -> str:
    return f"1.{stock_code}" if stock_code.startswith(("6", "9")) else f"0.{stock_code}"


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://quote.eastmoney.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _eastmoney_scaled(value: object) -> float | None:
    if value in {None, "", "-"}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isinstance(value, int):
        return round(number / 100, 4)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return round(number / 100, 4)
    return number


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
