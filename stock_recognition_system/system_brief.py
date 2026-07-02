from __future__ import annotations

import json
from pathlib import Path

from .simulation import ACTIVE_STATUSES, load_simulations, summarize_simulations
from .source_registry import list_external_sources


def build_system_brief(record_dir: str | Path = "records") -> dict[str, object]:
    record_path = Path(record_dir)
    simulations = load_simulations(record_path, include_closed=True)
    latest_summary = _load_latest_summary(record_path)
    external_sources = [source.to_dict() for source in list_external_sources()]
    active_simulations = [_simulation_row(item) for item in simulations if item.status in ACTIVE_STATUSES]
    closed_simulations = [_simulation_row(item) for item in simulations if item.status not in ACTIVE_STATUSES]

    return {
        "project": {
            "name": "stock-recognition-system",
            "positioning": "A-share group-message recognition, risk review, paper simulation, and beginner trade workflow.",
            "primary_user": "Beginner A-share trader with about 34,000 CNY capital.",
            "default_account_value": 34000,
            "trade_style": "4-5 day short-term training, no automatic real trading.",
        },
        "core_rules": [
            "Group messages are clues, not buy commands.",
            "No current or message-time price means no executable real trade.",
            "Do not chase limit-up stocks or prices above target/training executable price.",
            "Real 100-share training needs a valid price, stop, take-profit, capped one-lot loss, and acceptable risk/reward.",
            "A/B/C/D tiers are execution labels: A real 100 shares, B light 100 shares, C simulation, D abandon.",
            "Use daily-timing to estimate conditional buy timing for mentioned stocks already in the simulation watchlist.",
            "External screeners such as WenCai/iFind can provide candidates or evidence only; they cannot upgrade a buy.",
        ],
        "input_contracts": [
            {
                "scenario": "review_group_message",
                "required": ["raw_message", "push_date", "push_time", "current_price or auto_market_data"],
                "command": "python -m stock_recognition_system.cli review --message-file msg.txt --push-date YYYY-MM-DD --push-time HH:MM --auto-market-data --account-value 34000",
            },
            {
                "scenario": "paper_simulation",
                "required": ["reviewable message", "price evidence"],
                "command": "python -m stock_recognition_system.cli review --message-file msg.txt --current-price 10.00 --account-value 34000 --simulate",
            },
            {
                "scenario": "daily_buy_timing",
                "required": ["simulation watchlist", "market data or last close"],
                "command": "python -m stock_recognition_system.cli daily-timing --account-value 34000",
                "note": "Conditional timing only; 可考虑条件单 means alert/manual confirmation at or below the system price.",
            },
            {
                "scenario": "real_holding_monitor",
                "required": ["stock_code", "buy_price", "shares", "stop_loss", "take_profit"],
                "command": "python -m stock_recognition_system.cli holding-add --stock-code 300001 --buy-price 10 --shares 100 --stop-loss 9.5 --take-profit 11",
            },
            {
                "scenario": "research_candidate",
                "required": ["query"],
                "command": "python -m stock_recognition_system.cli research-wencai --query \"今日强势但未涨停\"",
                "note": "Research-only stub by default; candidates still need review and simulation.",
            },
        ],
        "output_contracts": [
            {"format": "markdown", "use": "Human-readable full report."},
            {"format": "json", "use": "Complete structured handoff."},
            {"format": "json-compact", "use": "Low-token AI handoff for one stock review."},
            {"format": "ai-brief", "use": "Short chat summary under about 120 Chinese characters."},
            {"format": "daily-timing", "use": "Daily conditional buy timing for stocks the user already mentioned."},
            {"format": "system-brief", "use": "Project-level context for Codex or another AI before continuing work."},
        ],
        "current_state": {
            "simulation_summary": summarize_simulations(simulations),
            "latest_simulation_summary": latest_summary,
            "active_simulations": active_simulations,
            "closed_simulations_count": len(closed_simulations),
        },
        "external_source_policy": {
            "enabled_market_sources": [
                item["source_id"] for item in external_sources if item["enabled_by_default"] and item["can_drive_decision"]
            ],
            "research_only_sources": [item["source_id"] for item in external_sources if not item["can_drive_decision"]],
            "rule": "Community or scraped sources are disabled by default and cannot drive real-trade decisions.",
        },
        "next_priorities": [
            "Add data quality report objects for every market-data fetch.",
            "Add compliant source adapters only after source registry review.",
            "Improve candidate-to-review pipeline after enough simulation samples exist.",
            "Add industry concentration control for real holdings.",
            "Accumulate at least 20-50 outcomes before loosening thresholds.",
        ],
    }


def build_system_brief_markdown(record_dir: str | Path = "records") -> str:
    brief = build_system_brief(record_dir)
    project = brief["project"]
    state = brief["current_state"]
    summary = state["simulation_summary"]
    latest = state["latest_simulation_summary"] or {}

    lines = [
        "# Stock Recognition System Brief",
        "",
        "## Positioning",
        f"- Project: {project['name']}",
        f"- User: {project['primary_user']}",
        f"- Mode: {project['trade_style']}",
        f"- Default account: {project['default_account_value']}",
        "",
        "## Core Rules",
    ]
    lines.extend(f"- {item}" for item in brief["core_rules"])
    lines.extend(
        [
            "",
            "## Current Simulation State",
            f"- Latest summary date: {latest.get('date', '-')}",
            f"- Generated at: {latest.get('generated_at', '-')}",
            f"- Total: {summary['total']}",
            f"- Active: {summary['active']}",
            f"- Closed: {summary['closed']}",
            f"- Net planned cash: {summary['net_planned_cash']:.2f}",
            "",
            "## Active Simulations",
        ]
    )
    active = state["active_simulations"]
    if active:
        for item in active:
            lines.append(
                f"- {item['stock_name'] or '-'} {item['stock_code'] or '-'} | {item['status']} | "
                f"entry {item['entry_price']:.2f} | TP {item['take_profit']:.2f} | SL {item['stop_loss']:.2f}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Input Contracts"])
    for item in brief["input_contracts"]:
        lines.append(f"- {item['scenario']}: `{item['command']}`")

    lines.extend(["", "## Output Contracts"])
    for item in brief["output_contracts"]:
        lines.append(f"- {item['format']}: {item['use']}")

    lines.extend(
        [
            "",
            "## External Source Policy",
            f"- Enabled market sources: {', '.join(brief['external_source_policy']['enabled_market_sources'])}",
            f"- Research-only sources: {', '.join(brief['external_source_policy']['research_only_sources'])}",
            f"- Rule: {brief['external_source_policy']['rule']}",
            "",
            "## Next Priorities",
        ]
    )
    lines.extend(f"- {item}" for item in brief["next_priorities"])
    lines.append("")
    return "\n".join(lines)


def _load_latest_summary(record_dir: Path) -> dict[str, object] | None:
    path = record_dir / "latest-simulation-summary.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"warning": "latest-simulation-summary.json is not valid JSON"}
    return {
        "date": payload.get("date"),
        "generated_at": payload.get("generated_at"),
        "source": payload.get("source"),
        "summary": payload.get("summary"),
    }


def _simulation_row(position) -> dict[str, object]:
    return {
        "id": position.id,
        "stock_code": position.stock_code,
        "stock_name": position.stock_name,
        "status": position.status,
        "entry_price": position.entry_price,
        "take_profit": position.take_profit,
        "stop_loss": position.stop_loss,
        "shares": position.shares,
        "last_close_price": position.last_close_price,
        "entry_triggered_date": position.entry_triggered_date,
        "exit_date": position.exit_date,
    }
