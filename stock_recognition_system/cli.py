from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import StockRecognitionEngine
from .followup import load_pending_follow_ups
from .models import GroupMessage, MarketEvidence
from .records import append_review_report


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
    evidence = MarketEvidence(
        current_price=args.current_price,
        change_pct=args.change_pct,
        five_day_change_pct=args.five_day_change_pct,
        twenty_day_change_pct=args.twenty_day_change_pct,
        volume_ratio=args.volume_ratio,
        is_limit_up=True if args.is_limit_up else None,
        market_index_change_pct=args.market_index_change_pct,
        sector_change_pct=args.sector_change_pct,
        close_prices=_parse_prices(args.close_prices),
        verified_claims=_parse_verified_claims(args.verified_claim),
        data_warnings=["CLI manual input"],
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
