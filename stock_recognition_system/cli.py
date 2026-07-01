from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .eastmoney import EastMoneyDailyDataProvider
from .engine import StockRecognitionEngine
from .evidence_playbook import build_evidence_requirements
from .followup import load_pending_follow_ups
from .models import EvidenceRequirement, GroupMessage, InformationSource, MarketEvidence, SignalAction, SourceTier
from .parser import parse_group_message
from .records import (
    SourceOutcome,
    append_review_report,
    append_source_outcome,
    load_source_outcomes,
    parse_signal_action,
    score_source_quality,
)
from .tencent import TencentDailyDataProvider, TencentIntradayDataProvider


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

    evidence_parser = subparsers.add_parser("evidence-plan", help="输出推荐逻辑需要采集和核验的数据")
    evidence_parser.add_argument("--message", help="直接输入群消息文本")
    evidence_parser.add_argument("--message-file", help="从文本文件读取群消息")

    pending_parser = subparsers.add_parser("pending", help="查看到期复盘任务")
    pending_parser.add_argument("--record-dir", default="records", help="复盘任务目录")

    outcome_parser = subparsers.add_parser("outcome", help="记录一条复盘结果")
    outcome_parser.add_argument("--record-dir", default="records", help="复盘结果目录")
    outcome_parser.add_argument("--stock-code", help="股票代码")
    outcome_parser.add_argument("--stock-name", help="股票名称")
    outcome_parser.add_argument("--source", default="group", help="群源或消息来源")
    outcome_parser.add_argument("--push-date", help="消息推送日期，例如 2026-06-29")
    outcome_parser.add_argument("--push-time", help="消息推送时间，例如 14:50")
    outcome_parser.add_argument("--review-date", help="复盘日期，例如 2026-07-04")
    outcome_parser.add_argument("--action", default=SignalAction.OBSERVE.value, help="系统当时动作，可用中文或枚举名")
    outcome_parser.add_argument("--signal-price", type=float, help="消息发出时或看到时价格")
    outcome_parser.add_argument("--target-price", type=float, help="目标价")
    outcome_parser.add_argument("--stop-loss", type=float, help="止损价")
    outcome_parser.add_argument("--max-price", type=float, help="复盘周期内最高价")
    outcome_parser.add_argument("--min-price", type=float, help="复盘周期内最低价")
    outcome_parser.add_argument("--close-price", type=float, help="复盘日收盘价")
    outcome_parser.add_argument("--reached-target", action="store_true", help="确认触达目标价")
    outcome_parser.add_argument("--hit-stop-loss", action="store_true", help="确认触发止损价")
    outcome_parser.add_argument("--late-push", action="store_true", help="确认尾盘推送")
    outcome_parser.add_argument("--chased-after-target", action="store_true", help="确认超过目标或涨停后才看到")
    outcome_parser.add_argument("--note", default="", help="复盘备注")

    score_parser = subparsers.add_parser("source-score", help="按复盘样本统计群源质量")
    score_parser.add_argument("--record-dir", default="records", help="复盘结果目录")
    score_parser.add_argument("--source", help="只统计指定群源")

    args = parser.parse_args(argv)
    if args.command == "review":
        return _review(args)
    if args.command == "evidence-plan":
        return _evidence_plan(args)
    if args.command == "pending":
        return _pending(args)
    if args.command == "outcome":
        return _outcome(args)
    if args.command == "source-score":
        return _source_score(args)
    return 2


def _review(args: argparse.Namespace) -> int:
    raw_text = _read_message(args.message, args.message_file)
    auto_enabled = args.auto_eastmoney or args.auto_market_data
    auto_evidence = _fetch_auto_evidence(raw_text, auto_enabled, args.history_days)
    message_time_evidence = _fetch_message_time_evidence(
        raw_text,
        auto_enabled and args.current_price is None,
        args.push_date,
        args.push_time,
    )
    manual_close_prices = _parse_prices(args.close_prices)
    manual_sources = _manual_sources(args, manual_close_prices)
    manual_warnings = ["CLI manual input"] if manual_sources else []
    current_price = _prefer_manual(
        args.current_price,
        _prefer_manual(message_time_evidence.current_price, auto_evidence.current_price),
    )
    change_pct = _prefer_manual(args.change_pct, _prefer_manual(message_time_evidence.change_pct, auto_evidence.change_pct))
    is_limit_up = True if args.is_limit_up else _prefer_manual(message_time_evidence.is_limit_up, auto_evidence.is_limit_up)
    evidence = MarketEvidence(
        current_price=current_price,
        change_pct=change_pct,
        five_day_change_pct=args.five_day_change_pct,
        twenty_day_change_pct=args.twenty_day_change_pct,
        volume_ratio=_prefer_manual(args.volume_ratio, auto_evidence.volume_ratio),
        turnover_rate=auto_evidence.turnover_rate,
        is_limit_up=is_limit_up,
        market_index_change_pct=args.market_index_change_pct,
        sector_change_pct=args.sector_change_pct,
        close_prices=manual_close_prices or auto_evidence.close_prices,
        verified_claims=_parse_verified_claims(args.verified_claim),
        data_warnings=manual_warnings + message_time_evidence.data_warnings + auto_evidence.data_warnings,
        information_sources=manual_sources + message_time_evidence.information_sources + auto_evidence.information_sources,
        raw=_combined_raw(message_time_evidence, auto_evidence),
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


def _evidence_plan(args: argparse.Namespace) -> int:
    raw_text = _read_message(args.message, args.message_file)
    parsed = parse_group_message(GroupMessage(raw_text=raw_text))
    title = "未知股票"
    if parsed.stock_name and parsed.stock_code:
        title = f"{parsed.stock_name} {parsed.stock_code}"
    elif parsed.stock_code:
        title = parsed.stock_code

    print(f"股票：{title}")
    print(f"推荐逻辑：{'、'.join(parsed.claimed_logic) if parsed.claimed_logic else '-'}")
    print("")
    _print_evidence_requirements(build_evidence_requirements(parsed.claimed_logic))
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


def _outcome(args: argparse.Namespace) -> int:
    outcome = SourceOutcome(
        action=parse_signal_action(args.action),
        stock_code=args.stock_code,
        stock_name=args.stock_name,
        source=args.source,
        push_date=args.push_date,
        push_time=args.push_time,
        review_date=args.review_date,
        reached_target=args.reached_target or _price_reached(args.max_price, args.target_price),
        hit_stop_loss=args.hit_stop_loss or _price_broke(args.min_price, args.stop_loss),
        late_push=args.late_push or _is_late_push(args.push_time),
        chased_after_target=args.chased_after_target or _price_reached(args.signal_price, args.target_price),
        signal_price=args.signal_price,
        target_price=args.target_price,
        stop_loss=args.stop_loss,
        max_price=args.max_price,
        min_price=args.min_price,
        close_price=args.close_price,
        note=args.note,
    )
    path = append_source_outcome(args.record_dir, outcome)
    print(f"已记录复盘结果：{path}")
    _print_source_score(load_source_outcomes(args.record_dir, args.source))
    return 0


def _source_score(args: argparse.Namespace) -> int:
    outcomes = load_source_outcomes(args.record_dir, args.source)
    _print_source_score(outcomes)
    return 0


def _print_source_score(outcomes: list[SourceOutcome]) -> None:
    score = score_source_quality(outcomes)
    print(f"样本数：{score['sample_size']}")
    print(f"评级：{score['grade']}")
    if "score" in score:
        print(f"分数：{score['score']}")
        print(f"触达目标率：{score['target_hit_rate']:.2%}")
        print(f"止损率：{score['stop_loss_rate']:.2%}")
        print(f"尾盘率：{score['late_push_rate']:.2%}")
        print(f"追高率：{score['chase_case_rate']:.2%}")
    for note in score.get("notes", []):
        print(f"- {note}")


def _print_evidence_requirements(requirements: list[EvidenceRequirement]) -> None:
    print("证据采集计划：")
    for item in requirements:
        print(f"- [{item.priority}] {item.claim}：{item.category}")
        if item.required_sources:
            print(f"  来源：{'；'.join(item.required_sources)}")
        if item.collect:
            print(f"  采集：{'；'.join(item.collect)}")
        if item.pass_criteria:
            print(f"  通过：{'；'.join(item.pass_criteria)}")
        if item.reject_criteria:
            print(f"  否决：{'；'.join(item.reject_criteria)}")
        if item.notes:
            print(f"  备注：{'；'.join(item.notes)}")


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


def _fetch_message_time_evidence(
    raw_text: str,
    enabled: bool,
    push_date: str | None,
    push_time: str | None,
) -> MarketEvidence:
    if not enabled or not push_date or not push_time:
        return MarketEvidence()
    stock_code = _extract_stock_code(raw_text)
    if not stock_code:
        return MarketEvidence(data_warnings=["无法识别股票代码，未拉取消息时分时价格"])
    try:
        return TencentIntradayDataProvider().get_evidence_at(stock_code, push_date, push_time)
    except Exception as exc:
        return MarketEvidence(data_warnings=[f"TencentIntradayDataProvider 失败：{exc}"])


def _combined_raw(message_time_evidence: MarketEvidence, auto_evidence: MarketEvidence) -> dict[str, object]:
    raw: dict[str, object] = {}
    if message_time_evidence.raw:
        raw["message_time_price"] = message_time_evidence.raw
    if auto_evidence.raw:
        raw["auto_market_data"] = auto_evidence.raw
    return raw


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


def _price_reached(price: float | None, target_price: float | None) -> bool:
    return price is not None and target_price is not None and price >= target_price


def _price_broke(price: float | None, stop_loss: float | None) -> bool:
    return price is not None and stop_loss is not None and price <= stop_loss


def _is_late_push(push_time: str | None) -> bool:
    if not push_time:
        return False
    match = re.match(r"^(\d{1,2}):(\d{2})$", push_time.strip())
    if not match:
        return False
    hour = int(match.group(1))
    minute = int(match.group(2))
    return (hour, minute) >= (14, 30)


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
