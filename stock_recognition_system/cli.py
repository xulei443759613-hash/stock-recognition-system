from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path

from .alerts import build_holding_alert, build_simulation_alerts
from .ai_output import build_ai_brief, build_compact_review
from .eastmoney import EastMoneyDailyDataProvider
from .engine import StockRecognitionEngine
from .evidence_playbook import build_evidence_requirements
from .followup import load_pending_follow_ups
from .holdings import (
    append_holding,
    create_holding,
    create_holding_from_simulation,
    load_holdings,
    monitor_holding,
)
from .models import EvidenceRequirement, GroupMessage, InformationSource, MarketEvidence, SignalAction, SourceTier
from .parser import parse_group_message
from .portfolio import build_portfolio_risk_report
from .records import (
    SourceOutcome,
    append_review_report,
    append_source_outcome,
    classify_opportunity_outcome,
    load_source_outcomes,
    parse_signal_action,
    score_source_quality,
)
from .simulation import (
    append_simulation_summary_record,
    load_simulations,
    open_simulation_from_result,
    summarize_simulations,
    update_simulation,
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
    review_parser.add_argument("--simulate", action="store_true", help="把本次分析加入模拟观察池")
    review_parser.add_argument(
        "--format",
        choices=["markdown", "json", "json-compact", "ai-brief"],
        default="markdown",
        help="输出格式",
    )
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

    sim_list_parser = subparsers.add_parser("simulate-list", help="查看模拟观察池")
    sim_list_parser.add_argument("--record-dir", default="records", help="模拟观察目录")
    sim_list_parser.add_argument("--status", help="只查看指定状态，例如 等待入场、模拟持仓、模拟止盈、模拟止损")
    sim_list_parser.add_argument("--all", action="store_true", help="包含已结束记录")

    sim_update_parser = subparsers.add_parser("simulate-update", help="更新一条模拟观察")
    sim_update_parser.add_argument("--record-dir", default="records", help="模拟观察目录")
    sim_update_parser.add_argument("--id", required=True, help="模拟观察 ID")
    sim_update_parser.add_argument("--as-of", help="复盘日期，例如 2026-07-02")
    sim_update_parser.add_argument("--high-price", type=float, help="复盘周期最高价")
    sim_update_parser.add_argument("--low-price", type=float, help="复盘周期最低价")
    sim_update_parser.add_argument("--close-price", type=float, help="复盘收盘价")
    sim_update_parser.add_argument("--note", default="", help="备注")

    sim_refresh_parser = subparsers.add_parser("simulate-refresh", help="自动拉取行情并刷新模拟观察池")
    sim_refresh_parser.add_argument("--record-dir", default="records", help="模拟观察目录")
    sim_refresh_parser.add_argument("--history-days", type=int, default=5, help="自动行情读取的日线数量")
    sim_refresh_parser.add_argument("--as-of", help="复盘日期，例如 2026-07-02")
    sim_refresh_parser.add_argument("--save-summary", action="store_true", help="刷新后追加写入每日模拟汇总数据库")

    sim_summary_parser = subparsers.add_parser("simulate-summary", help="汇总模拟观察结果")
    sim_summary_parser.add_argument("--record-dir", default="records", help="模拟观察目录")
    sim_summary_parser.add_argument("--all", action="store_true", help="包含已结束记录")
    sim_summary_parser.add_argument("--save", action="store_true", help="追加写入每日模拟汇总数据库")

    holding_add_parser = subparsers.add_parser("holding-add", help="新增真实持仓记录")
    holding_add_parser.add_argument("--record-dir", default="records", help="持仓记录目录")
    holding_add_parser.add_argument("--from-simulation-id", help="从模拟观察升级为真实持仓")
    holding_add_parser.add_argument("--stock-code", help="股票代码")
    holding_add_parser.add_argument("--stock-name", help="股票名称")
    holding_add_parser.add_argument("--buy-price", type=float, help="买入价")
    holding_add_parser.add_argument("--shares", type=int, default=100, help="股数")
    holding_add_parser.add_argument("--buy-date", help="买入日期，例如 2026-07-01")
    holding_add_parser.add_argument("--stop-loss", type=float, help="止损价")
    holding_add_parser.add_argument("--take-profit", type=float, help="止盈价")
    holding_add_parser.add_argument("--note", default="", help="备注")

    holding_list_parser = subparsers.add_parser("holding-list", help="查看真实持仓")
    holding_list_parser.add_argument("--record-dir", default="records", help="持仓记录目录")
    holding_list_parser.add_argument("--all", action="store_true", help="包含已关闭持仓")

    monitor_parser = subparsers.add_parser("monitor", help="批量检查真实持仓卖出信号")
    monitor_parser.add_argument("--record-dir", default="records", help="持仓记录目录")
    monitor_parser.add_argument("--history-days", type=int, default=5, help="自动行情读取的日线数量")
    monitor_parser.add_argument("--stock-code", help="只检查指定股票代码")
    monitor_parser.add_argument("--current-price", type=float, help="手动当前价/收盘价")
    monitor_parser.add_argument("--high-price", type=float, help="手动周期最高价")
    monitor_parser.add_argument("--low-price", type=float, help="手动周期最低价")

    alert_parser = subparsers.add_parser("alert", help="检查模拟观察池和真实持仓触发提醒")
    alert_parser.add_argument("--record-dir", default="records", help="记录目录")
    alert_parser.add_argument("--history-days", type=int, default=5, help="自动行情读取的日线数量")
    alert_parser.add_argument("--stock-code", help="只检查指定股票代码")

    portfolio_parser = subparsers.add_parser("portfolio", help="汇总真实持仓组合风险")
    portfolio_parser.add_argument("--record-dir", default="records", help="持仓记录目录")
    portfolio_parser.add_argument("--account-value", type=float, default=34000.0, help="账户总金额")
    portfolio_parser.add_argument("--history-days", type=int, default=5, help="自动行情读取的日线数量")
    portfolio_parser.add_argument("--use-buy-price", action="store_true", help="不用联网行情，按买入价估算组合风险")

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
    if args.command == "simulate-list":
        return _simulate_list(args)
    if args.command == "simulate-update":
        return _simulate_update(args)
    if args.command == "simulate-refresh":
        return _simulate_refresh(args)
    if args.command == "simulate-summary":
        return _simulate_summary(args)
    if args.command == "holding-add":
        return _holding_add(args)
    if args.command == "holding-list":
        return _holding_list(args)
    if args.command == "monitor":
        return _monitor(args)
    if args.command == "alert":
        return _alert(args)
    if args.command == "portfolio":
        return _portfolio(args)
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

    if args.format == "markdown":
        output_text = result.report
    elif args.format == "json":
        output_text = json.dumps(_jsonable(result), ensure_ascii=False, indent=2)
    elif args.format == "json-compact":
        output_text = json.dumps(build_compact_review(result), ensure_ascii=False, indent=2)
    else:
        output_text = build_ai_brief(result)
    print(output_text)
    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
    if args.save:
        path = append_review_report(args.record_dir, result)
        print(f"\n已保存报告：{path}")
    if args.simulate:
        try:
            position = open_simulation_from_result(args.record_dir, result, args.source, args.push_date, args.push_time)
        except ValueError as exc:
            print(f"\n未创建模拟观察：{exc}")
        else:
            print(f"\n已加入模拟观察：{position.id}")
            _print_simulation(position)
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
    missed_review = classify_opportunity_outcome(outcome)
    print(f"机会复盘：{missed_review['status']}")
    if missed_review.get("executable_max_buy_price") is not None:
        print(f"训练模式可执行价：{missed_review['executable_max_buy_price']:.2f}")
    _print_source_score(load_source_outcomes(args.record_dir, args.source))
    return 0


def _source_score(args: argparse.Namespace) -> int:
    outcomes = load_source_outcomes(args.record_dir, args.source)
    _print_source_score(outcomes)
    return 0


def _simulate_list(args: argparse.Namespace) -> int:
    simulations = load_simulations(args.record_dir, status=args.status, include_closed=args.all)
    if not simulations:
        print("模拟观察池为空")
        return 0
    for position in simulations:
        _print_simulation(position)
    return 0


def _simulate_update(args: argparse.Namespace) -> int:
    position = update_simulation(
        args.record_dir,
        args.id,
        high_price=args.high_price,
        low_price=args.low_price,
        close_price=args.close_price,
        as_of=args.as_of,
        note=args.note,
    )
    print("已更新模拟观察")
    _print_simulation(position)
    return 0


def _simulate_refresh(args: argparse.Namespace) -> int:
    active_positions = load_simulations(args.record_dir)
    if not active_positions:
        print("模拟观察池没有活跃记录")
        return 0

    updated = 0
    for position in active_positions:
        if not position.stock_code:
            print(f"跳过 {position.id}：缺股票代码")
            continue
        evidence = _fetch_simulation_market_data(position.stock_code, args.history_days)
        high_price, low_price, close_price, trade_date = _latest_ohlc_from_evidence(evidence)
        if close_price is None and evidence.current_price is None:
            print(f"跳过 {position.id}：未取到可用价格；{'；'.join(evidence.data_warnings)}")
            continue
        fallback_price = evidence.current_price
        close_price = close_price if close_price is not None else fallback_price
        high_price = high_price if high_price is not None else close_price
        low_price = low_price if low_price is not None else close_price
        note = "；".join(evidence.data_warnings)
        refreshed = update_simulation(
            args.record_dir,
            position.id,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            as_of=args.as_of or trade_date,
            note=note,
        )
        updated += 1
        _print_simulation(refreshed)

    print("")
    print(f"本次更新：{updated}/{len(active_positions)}")
    all_positions = load_simulations(args.record_dir, include_closed=True)
    _print_simulation_summary(all_positions)
    if args.save_summary:
        path, _ = append_simulation_summary_record(
            args.record_dir,
            all_positions,
            as_of=args.as_of,
            source="simulate-refresh",
        )
        print(f"已写入模拟汇总数据库：{path}")
    return 0


def _simulate_summary(args: argparse.Namespace) -> int:
    positions = load_simulations(args.record_dir, include_closed=args.all)
    _print_simulation_summary(positions)
    if args.save:
        path, _ = append_simulation_summary_record(args.record_dir, positions, source="simulate-summary")
        print(f"已写入模拟汇总数据库：{path}")
    return 0


def _holding_add(args: argparse.Namespace) -> int:
    if args.from_simulation_id:
        simulations = load_simulations(args.record_dir, include_closed=True)
        simulation = next((item for item in simulations if item.id == args.from_simulation_id), None)
        if simulation is None:
            raise SystemExit(f"未找到模拟观察：{args.from_simulation_id}")
        holding = create_holding_from_simulation(simulation, buy_date=args.buy_date, shares=args.shares)
    else:
        if not args.stock_code or args.buy_price is None:
            raise SystemExit("手动新增持仓必须提供 --stock-code 和 --buy-price")
        holding = create_holding(
            stock_code=args.stock_code,
            stock_name=args.stock_name,
            buy_price=args.buy_price,
            shares=args.shares,
            buy_date=args.buy_date,
            stop_loss=args.stop_loss,
            take_profit=args.take_profit,
            source="manual",
            note=args.note,
        )
    append_holding(args.record_dir, holding)
    print("已新增真实持仓")
    _print_holding(holding)
    return 0


def _holding_list(args: argparse.Namespace) -> int:
    holdings = load_holdings(args.record_dir, include_closed=args.all)
    if not holdings:
        print("没有真实持仓记录")
        return 0
    for holding in holdings:
        _print_holding(holding)
    return 0


def _monitor(args: argparse.Namespace) -> int:
    holdings = load_holdings(args.record_dir)
    if args.stock_code:
        holdings = [item for item in holdings if item.stock_code == args.stock_code]
    if not holdings:
        print("没有持有中的真实持仓")
        return 0
    manual_prices = any(value is not None for value in [args.current_price, args.high_price, args.low_price])
    if manual_prices and not args.stock_code and len(holdings) > 1:
        raise SystemExit("手动价格监控多只持仓时必须提供 --stock-code")
    for holding in holdings:
        if manual_prices:
            high_price = args.high_price
            low_price = args.low_price
            current_price = args.current_price
        else:
            evidence = _fetch_simulation_market_data(holding.stock_code, args.history_days)
            high_price, low_price, close_price, _ = _latest_ohlc_from_evidence(evidence)
            current_price = close_price if close_price is not None else evidence.current_price
        signal = monitor_holding(holding, current_price=current_price, high_price=high_price, low_price=low_price)
        _print_sell_signal(signal)
    return 0


def _alert(args: argparse.Namespace) -> int:
    alerts = []
    checked = 0

    simulations = load_simulations(args.record_dir)
    if args.stock_code:
        simulations = [item for item in simulations if item.stock_code == args.stock_code]
    for position in simulations:
        if not position.stock_code:
            continue
        evidence = _fetch_simulation_market_data(position.stock_code, args.history_days)
        high_price, low_price, close_price, _ = _latest_ohlc_from_evidence(evidence)
        current_price = close_price if close_price is not None else evidence.current_price
        if current_price is None:
            print(f"跳过模拟 {position.id}：未取到可用价格")
            continue
        high_price = high_price if high_price is not None else current_price
        low_price = low_price if low_price is not None else current_price
        checked += 1
        alerts.extend(
            build_simulation_alerts(
                position,
                high_price=high_price,
                low_price=low_price,
                close_price=current_price,
            )
        )

    holdings = load_holdings(args.record_dir)
    if args.stock_code:
        holdings = [item for item in holdings if item.stock_code == args.stock_code]
    for holding in holdings:
        evidence = _fetch_simulation_market_data(holding.stock_code, args.history_days)
        high_price, low_price, close_price, _ = _latest_ohlc_from_evidence(evidence)
        current_price = close_price if close_price is not None else evidence.current_price
        if current_price is None:
            print(f"跳过持仓 {holding.id}：未取到可用价格")
            continue
        high_price = high_price if high_price is not None else current_price
        low_price = low_price if low_price is not None else current_price
        checked += 1
        alert = build_holding_alert(
            monitor_holding(holding, current_price=current_price, high_price=high_price, low_price=low_price)
        )
        if alert is not None:
            alerts.append(alert)

    if not alerts:
        print(f"没有触发提醒，已检查 {checked} 条记录")
        return 0

    print(f"触发提醒：{len(alerts)} 条（已检查 {checked} 条记录）")
    for alert in alerts:
        _print_alert(alert)
    return 0


def _portfolio(args: argparse.Namespace) -> int:
    holdings = load_holdings(args.record_dir)
    if not holdings:
        print("没有持有中的真实持仓")
        return 0
    current_prices: dict[str, float] = {}
    if not args.use_buy_price:
        for holding in holdings:
            evidence = _fetch_simulation_market_data(holding.stock_code, args.history_days)
            _, _, close_price, _ = _latest_ohlc_from_evidence(evidence)
            price = close_price if close_price is not None else evidence.current_price
            if price is not None:
                current_prices[holding.stock_code] = price
    report = build_portfolio_risk_report(holdings, current_prices=current_prices, account_value=args.account_value)
    _print_portfolio_report(report)
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
        print(f"未实盘后触达目标率：{score['no_trade_target_hit_rate']:.2%}")
        print(f"可执行错失率：{score['actionable_missed_rate']:.2%}")
        print(f"非可执行上涨率：{score['non_actionable_runup_rate']:.2%}")
        print(f"顺序待查率：{score['ambiguous_missed_rate']:.2%}")
    for note in score.get("notes", []):
        print(f"- {note}")


def _print_simulation(position) -> None:
    print(
        f"{position.id} {position.stock_name or '-'} {position.stock_code or '-'} "
        f"{position.status} 入场 {position.entry_price:.2f} "
        f"止盈 {position.take_profit:.2f} 止损 {position.stop_loss:.2f}"
    )
    if position.planned_cash is not None:
        print(f"  100股占用：{position.planned_cash:.2f}")
    if position.planned_profit_cash is not None:
        print(f"  触发止盈预计盈利：{position.planned_profit_cash:.2f}")
    if position.planned_loss_cash is not None:
        print(f"  触发止损预计亏损：{position.planned_loss_cash:.2f}")
    if position.last_close_price is not None:
        print(f"  最近收盘：{position.last_close_price:.2f}")
    if position.entry_triggered_date:
        print(f"  模拟入场日：{position.entry_triggered_date}")
    if position.exit_date:
        print(f"  模拟结束日：{position.exit_date}")


def _print_simulation_summary(positions) -> None:
    summary = summarize_simulations(positions)
    print("模拟观察汇总")
    print(f"  总数：{summary['total']}")
    print(f"  活跃：{summary['active']}")
    print(f"  已结束：{summary['closed']}")
    by_status = summary["by_status"]
    for status, count in by_status.items():
        print(f"  {status}：{count}")
    print(f"  已止盈模拟盈利：{summary['planned_profit_cash']:.2f}")
    print(f"  已止损模拟亏损：{summary['planned_loss_cash']:.2f}")
    print(f"  模拟净额：{summary['net_planned_cash']:.2f}")


def _print_holding(holding) -> None:
    print(
        f"{holding.id} {holding.stock_name or '-'} {holding.stock_code} {holding.status} "
        f"买入 {holding.buy_price:.2f} 股数 {holding.shares} "
        f"止盈 {_fmt_price(holding.take_profit)} 止损 {_fmt_price(holding.stop_loss)}"
    )
    if holding.buy_date:
        print(f"  买入日：{holding.buy_date}")
    if holding.source:
        print(f"  来源：{holding.source}")
    if holding.note:
        print(f"  备注：{holding.note}")


def _print_sell_signal(signal) -> None:
    print(
        f"{signal.holding_id} {signal.stock_name or '-'} {signal.stock_code} "
        f"{signal.action} 现价 {_fmt_price(signal.current_price)} "
        f"浮盈亏 {_fmt_price(signal.pnl_cash)} ({_fmt_price(signal.pnl_pct)}%)"
    )
    if signal.high_price is not None or signal.low_price is not None:
        print(f"  最高 {_fmt_price(signal.high_price)} 最低 {_fmt_price(signal.low_price)}")
    for reason in signal.reasons:
        print(f"  原因：{reason}")


def _print_alert(alert) -> None:
    print(f"{alert.level} [{alert.source}] {alert.stock_name or '-'} {alert.stock_code or '-'}")
    print(f"  {alert.message}")
    print(
        f"  现价 {_fmt_price(alert.current_price)} "
        f"最高 {_fmt_price(alert.high_price)} 最低 {_fmt_price(alert.low_price)}"
    )


def _print_portfolio_report(report) -> None:
    print("组合风险汇总")
    print(f"  账户金额：{report.account_value:.2f}")
    print(f"  持仓数量：{report.holdings_count}")
    print(f"  持仓市值：{report.total_market_value:.2f}")
    print(f"  持仓占比：{report.exposure_pct:.2f}%")
    print(f"  计划止损亏损：{report.total_planned_loss_cash:.2f}")
    print(f"  计划止损占比：{report.planned_loss_pct:.2f}%")
    for row in report.rows:
        loss = "-" if row.planned_loss_cash is None else f"{row.planned_loss_cash:.2f}"
        print(
            f"  {row.stock_name or '-'} {row.stock_code}: "
            f"{row.shares}股 现价{row.current_price:.2f} 市值{row.market_value:.2f} 止损风险{loss}"
        )
    for warning in report.warnings:
        print(f"  警告：{warning}")


def _fmt_price(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _fetch_simulation_market_data(stock_code: str, history_days: int) -> MarketEvidence:
    warnings: list[str] = []
    for provider in [TencentDailyDataProvider(close_count=history_days), EastMoneyDailyDataProvider(close_count=history_days)]:
        try:
            evidence = provider.get_evidence(stock_code)
        except Exception as exc:
            warnings.append(f"{provider.__class__.__name__} 失败：{exc}")
            continue
        if evidence.current_price is not None or evidence.close_prices:
            evidence.data_warnings = warnings + evidence.data_warnings
            return evidence
        warnings.extend(evidence.data_warnings)
    return MarketEvidence(data_warnings=warnings + [f"{stock_code} 自动行情不可用"])


def _latest_ohlc_from_evidence(evidence: MarketEvidence) -> tuple[float | None, float | None, float | None, str | None]:
    raw_latest = (evidence.raw or {}).get("latest")
    if isinstance(raw_latest, list) and len(raw_latest) >= 5:
        return _safe_float(raw_latest[3]), _safe_float(raw_latest[4]), _safe_float(raw_latest[2]), str(raw_latest[0])
    if isinstance(raw_latest, str):
        parts = raw_latest.split(",")
        if len(parts) >= 5:
            return _safe_float(parts[3]), _safe_float(parts[4]), _safe_float(parts[2]), parts[0]
    return None, None, evidence.current_price, None


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _jsonable(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


if __name__ == "__main__":
    raise SystemExit(main())
