from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import MarketEvidence


@dataclass
class ManualDataProvider:
    """Manual provider for beginner-safe operation when no API is connected."""

    current_price: float | None = None
    change_pct: float | None = None
    is_limit_up: bool | None = None

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        return MarketEvidence(
            current_price=self.current_price,
            change_pct=self.change_pct,
            is_limit_up=self.is_limit_up,
            data_warnings=["manual data; official evidence not connected"],
            raw={"stock_code": stock_code},
        )


class DataProviderProtocol:
    """Interface for future AkShare/Tushare/CNINFO connectors."""

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        raise NotImplementedError


@dataclass
class AkShareDataProvider:
    """Optional AkShare provider. Requires `pip install akshare`."""

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:
            raise RuntimeError("AkShare is not installed. Install it before using AkShareDataProvider.") from exc

        spot = ak.stock_zh_a_spot_em()
        row = spot[spot["代码"].astype(str) == stock_code]
        if row.empty:
            return MarketEvidence(data_warnings=[f"AkShare 未找到股票代码 {stock_code}"], raw={"stock_code": stock_code})

        item = row.iloc[0].to_dict()
        current_price = _to_float(item.get("最新价"))
        change_pct = _to_float(item.get("涨跌幅"))
        turnover_rate = _to_float(item.get("换手率"))
        volume_ratio = _to_float(item.get("量比"))
        return MarketEvidence(
            current_price=current_price,
            change_pct=change_pct,
            turnover_rate=turnover_rate,
            volume_ratio=volume_ratio,
            is_limit_up=_is_probable_limit_up(change_pct),
            data_warnings=["AkShare 行情数据，仅用于风控核验"],
            raw=item,
        )


@dataclass
class TushareDataProvider:
    """Optional Tushare provider. Requires `pip install tushare` and a token."""

    token: str

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Tushare is not installed. Install it before using TushareDataProvider.") from exc

        pro = ts.pro_api(self.token)
        ts_code = _to_ts_code(stock_code)
        daily = pro.daily(ts_code=ts_code)
        if daily.empty:
            return MarketEvidence(data_warnings=[f"Tushare 未找到股票代码 {stock_code}"], raw={"stock_code": stock_code})

        latest = daily.sort_values("trade_date", ascending=False).iloc[0].to_dict()
        close = _to_float(latest.get("close"))
        pct_chg = _to_float(latest.get("pct_chg"))
        return MarketEvidence(
            current_price=close,
            change_pct=pct_chg,
            is_limit_up=_is_probable_limit_up(pct_chg),
            data_warnings=["Tushare 日线数据，仅用于风控核验"],
            raw=latest,
        )


@dataclass
class MergedDataProvider:
    """Try providers in order and merge the first usable market evidence."""

    providers: Iterable[DataProviderProtocol]

    def get_evidence(self, stock_code: str) -> MarketEvidence:
        warnings: list[str] = []
        for provider in self.providers:
            try:
                evidence = provider.get_evidence(stock_code)
            except Exception as exc:  # Keep data failures from becoming trade signals.
                warnings.append(f"{provider.__class__.__name__} 失败：{exc}")
                continue
            evidence.data_warnings.extend(warnings)
            return evidence
        return MarketEvidence(data_warnings=warnings or ["没有可用数据源"], raw={"stock_code": stock_code})


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_probable_limit_up(change_pct: float | None) -> bool | None:
    if change_pct is None:
        return None
    return change_pct >= 9.8


def _to_ts_code(stock_code: str) -> str:
    if stock_code.startswith(("6", "9")):
        return f"{stock_code}.SH"
    return f"{stock_code}.SZ"
