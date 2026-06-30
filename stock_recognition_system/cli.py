from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .eastmoney import EastMoneyDailyDataProvider
from .engine import StockRecognitionEngine
from .followup import load_pending_follow_ups
from .models import GroupMessage, InformationSource, MarketEvidence, SourceTier
from .records import append_review_report
from .tencent import TencentDailyDataProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stock-review", description="股票群消息风控分析工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser("review", help="分析一条群消息")
    review_parser.add_argument("--message", help="直接输入群消息文本")
    review_parser.add_argument("--message-file", help="从文本文件读取群消息")
    review_parser.add_argument("--push-date", help="推送日期，例如 2026-06-29")
    review_parser.add_argument("--push-time", help="推送时间，例如 14:40")
    review_parser.add_argument("--source", default="group", help="消息来源")
    review_parser.add_argument("--current-price", type=float, help="当前价")
    review_parser.add_argument("--change-pct", type=float, help="当日涨跌幅")
    review_parser.add_argument("--five-day-change-pct", type=float, help="5 日涨跌幅")
    review_parser.add_argument("--twenty-day-change-pct", type=float, help="20 日涨跌幅")
    review_parser.add_argument("--market-index-change-pct", type=float, help="大盘涨跌幅")
    review_parser.add_argument("--sector-change-pct", type=float, help="板块涨跌幅")
    review_parser.add_argument("--volume-ratio", type=float, help="量比")
    review_parser.add_argument("--is-limit-up", action="store_true", help="是否涨停或接近涨停")
    review_parser.add_argument("--close-prices", help="逗号分隔的近期收盘价，用于技术面体检")
    review_parser.add_argument("--auto-market-data", action="store_true", help="自动从公开行情接口拉取最近日线数据")
    review_parser.add_argument("--auto-eastmoney", action="store_true", help="兼容参数：优先东方财富，失败时使用腾讯行情")
    review_parser.add_argument("--history-days", type=int, default=20, help="自动行情读取的日线数量")
    review_parser.add_argument("--verified-claim", action="append", default=[], help="证据核验，格式：逻辑=true 或 逻辑=false")
    review_parser.add_argument("--account-value", type=float, help="账户总金额，用于仓位计划")
    review_parser.add_argument("--record-dir", default="records", help="报告和复盘任务保存目录")
    review_parser.add_argument("--save", action="store_true", help="保存报告和复盘任务")
    review_parser.add_argument("--output", help="另存报告到指定文件")

    pending_parser = subparsers.add_parser("pending", help="查看到期复盘任务")
    pending_parser.add_argument("--record-dir", default="records", help="复盘任务目录")

    args = parser.parse_args(argv)
    if args.command == "review":
        return _review(args)
    if args.command == "pending":
        return _pending(args)
    return 2


def _review(args: argparse.Namespace) -> int:
    raw_text = _read_message(args.message, args.message_file)
    auto_evidence = _fetch_auto_evidence(raw_text, args.auto_eastmoney or args.auto_market_data, args.history_days)
    manual_close_prices = _parse_prices(args.close_prices)
    manual_sources = _manual_sources(args, manual_close_prices)
    manual_warnings = ["CLI manual input"] if manual_sources else []
    evidence = MarketEvidence(
        current_price=_prefer_manual(args.current_price, auto_evidence.current_price),
        change_pct=_prefer_manual(args.change_pct, auto_evidence.change_pct),
        five_day_change_pct=args.five_day_change_pct,
        twenty_day_change_pct=args.twenty_day_change_pct,
        volume_ratio=_prefer_manual(args.volume_ratio, auto_evidence.volume_ratio),
        turnover_rate=auto_evidence.turnover_rate,
        is_limit_up=True if args.is_limit_up else auto_evidence.is_limit_up,
        market_index_change_pct=args.market_index_change_pct,
        sector_change_pct=args.sector_change_pct,
        close_prices=manual_close_prices or auto_evidence.close_prices,
        verified_claims=_parse_verified_claims(args.verified_claim),
        data_warnings=manual_warnings + auto_evidence.data_warnings,
        information_sources=manual_sources + auto_evidence.information_sources,
        raw={"auto_market_data": auto_evidence.raw} if auto_evidence.raw else {},
    )
    message = GroupMessage(raw_text=raw_text, push_time=args.push_time, push_date=args.push_date, source=args.source)
    result = StockRecognitionEngine().review(message, evidence, account_value=args.account_value)

    print(result.report)
    if args.output:
        Path(args.output).write_text(result.report, encoding="utf-8")
    if args.save:
        path = append_review_report(args.record_dir, result)
        print(f"\n已保存报告：{path}")
    return 0


def _pending(args: argparse.Namespace) -> int:
    tasks = load_pending_follow_ups(args.record_dir)
    if not tasks:
        print("没有到期复盘任务")
        return 0
    for task in tasks:
        label = task.stock_name or task.stock_code or "未知股票"
        print(f"{task.due_date} {label} {task.task_type}: {task.instruction}")
    return 0


def _read_message(message: str | None, message_file: str | None) -> str:
    if message:
        return message
    if message_file:
        return Path(message_file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("请提供 --message 或 --message-file")


def _fetch_auto_evidence(raw_text: str, enabled: bool, history_days: int) -> MarketEvidence:
    if not enabled:
        return MarketEvidence()
    stock_code = _extract_stock_code(raw_text)
    if not stock_code:
        raise SystemExit("无法从消息中识别股票代码，不能自动拉取公开行情")

    warnings: list[str] = []
    providers = [
        EastMoneyDailyDataProvider(close_count=history_days),
        TencentDailyDataProvider(close_count=history_days),
    ]
    for provider in providers:
        try:
            evidence = provider.get_evidence(stock_code)
        except Exception as exc:
            warnings.append(f"{provider.__class__.__name__} 失败：{exc}")
            continue
        if evidence.current_price is not None or evidence.close_prices:
            evidence.data_warnings = warnings + evidence.data_warnings
            return evidence
        warnings.extend(evidence.data_warnings)

    raise SystemExit("公开行情拉取失败：" + "；".join(warnings))


def _extract_stock_code(raw_text: str) -> str | None:
    match = re.search(r"(?<!\d)([0-9]{6})(?!\d)", raw_text)
    return match.group(1) if match else None


def _parse_prices(value: str | None) -> list[float]:
    if not value:
        return []
    prices: list[float] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        prices.append(float(item))
    return prices


def _prefer_manual(manual_value: float | None, automatic_value: float | None) -> float | None:
    return manual_value if manual_value is not None else automatic_value


def _manual_sources(args: argparse.Namespace, manual_close_prices: list[float]) -> list[InformationSource]:
    has_manual_data = any(
        value is not None
        for value in [
            args.current_price,
            args.change_pct,
            args.five_day_change_pct,
            args.twenty_day_change_pct,
            args.market_index_change_pct,
            args.sector_change_pct,
            args.volume_ratio,
        ]
    )
    has_manual_data = has_manual_data or args.is_limit_up or bool(manual_close_prices) or bool(args.verified_claim)
    if not has_manual_data:
        return []
    return [InformationSource("CLI manual input", SourceTier.UNKNOWN, note="手动行情或证据输入，需保留来源")]


def _parse_verified_claims(values: list[str]) -> dict[str, bool]:
    claims: dict[str, bool] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"证据核验格式错误：{value}")
        key, raw = value.split("=", 1)
        normalized = raw.strip().lower()
        if normalized not in {"true", "false", "1", "0", "yes", "no"}:
            raise SystemExit(f"证据核验值必须是 true/false：{value}")
        claims[key.strip()] = normalized in {"true", "1", "yes"}
    return claims


if __name__ == "__main__":
    raise SystemExit(main())
