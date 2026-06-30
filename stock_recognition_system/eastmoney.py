from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import urlopen

from .models import InformationSource, MarketEvidence, SourceTier


@dataclass
class EastMoneyDailyDataProvider:
    """Fetch recent daily closes from EastMoney public K-line API."""

    close_count: int = 20

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        secid = to_eastmoney_secid(stock_code)
        url = (
            "https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            "&fields1=f1,f2,f3,f4,f5,f6"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            "&klt=101&fqt=1&end=20500101"
            f"&lmt={max(1, self.close_count)}"
        )
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        klines = (payload.get("data") or {}).get("klines") or []
        parsed = parse_daily_klines(klines)
        source = InformationSource("东方财富", SourceTier.LICENSED_DATA_VENDOR, url="https://quote.eastmoney.com")
        if not parsed.close_prices:
            return MarketEvidence(
                data_warnings=[f"EastMoney 未返回 {stock_code} 日线数据"],
                information_sources=[source],
                raw={"stock_code": stock_code, "url": url, "payload": payload},
            )

        return MarketEvidence(
            current_price=parsed.close_prices[-1],
            change_pct=parsed.change_pct,
            turnover_rate=parsed.turnover_rate,
            close_prices=parsed.close_prices,
            is_limit_up=parsed.change_pct is not None and parsed.change_pct >= 9.8,
            data_warnings=["EastMoney 日线数据，仅用于风控核验；真实交易前需再次确认"],
            information_sources=[source],
            raw={"stock_code": stock_code, "url": url, "latest": parsed.latest_raw},
        )


@dataclass
class EastMoneyDailyKlines:
    close_prices: list[float]
    change_pct: float | None
    turnover_rate: float | None
    latest_raw: str | None


def parse_daily_klines(klines: list[str]) -> EastMoneyDailyKlines:
    close_prices: list[float] = []
    latest_raw: str | None = None
    change_pct: float | None = None
    turnover_rate: float | None = None
    for raw in klines:
        parts = raw.split(",")
        if len(parts) < 3:
            continue
        close = _to_float(parts[2])
        if close is None:
            continue
        close_prices.append(close)
        latest_raw = raw
        if len(parts) > 8:
            change_pct = _to_float(parts[8])
        if len(parts) > 10:
            turnover_rate = _to_float(parts[10])
    return EastMoneyDailyKlines(close_prices, change_pct, turnover_rate, latest_raw)


def to_eastmoney_secid(stock_code: str) -> str:
    return f"1.{stock_code}" if stock_code.startswith(("6", "9")) else f"0.{stock_code}"


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
