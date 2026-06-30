from __future__ import annotations

from .models import ReviewResult


def _fmt_price(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def build_markdown_report(result: ReviewResult) -> str:
    parsed = result.parsed
    lines: list[str] = []

    title = "未知股票"
    if parsed and parsed.stock_name and parsed.stock_code:
        title = f"{parsed.stock_name} {parsed.stock_code}"
    elif parsed and parsed.stock_code:
        title = parsed.stock_code

    lines.append(f"# 股票风控分析 - {title}")
    lines.append("")
    lines.append("## 结论")
    lines.append(f"- 动作信号：{result.action.value}")
    lines.append(f"- 置信度：{result.confidence}")
    lines.append(f"- 新手仓位上限：{result.max_position_pct:.2%}")
    if result.position_plan:
        lines.append(f"- 仓位说明：{result.position_plan.note}")
        if result.position_plan.max_shares is not None:
            lines.append(f"- 最大股数：{result.position_plan.max_shares}")
            lines.append(f"- 预计占用资金：{result.position_plan.cash_needed:.2f}")

    lines.append("")
    lines.append("## 核心原因")
    lines.extend(f"- {item}" for item in result.reasons)

    if parsed:
        lines.append("")
        lines.append("## 识别结果")
        lines.append(f"- 股票：{parsed.stock_name or '-'}")
        lines.append(f"- 代码：{parsed.stock_code or '-'}")
        lines.append(f"- 入场区间：{_fmt_price(parsed.entry_low)} - {_fmt_price(parsed.entry_high)}")
        lines.append(f"- 目标价：{_fmt_price(parsed.target_price)}")
        lines.append(f"- 止损价：{_fmt_price(parsed.stop_loss)}")
        lines.append(f"- 推荐逻辑：{'、'.join(parsed.claimed_logic) if parsed.claimed_logic else '-'}")
        if parsed.adviser_text:
            lines.append(f"- 投顾/来源文本：{parsed.adviser_text}")

    lines.append("")
    lines.append("## 风险提示")
    if result.red_flags:
        lines.extend(f"- {item}" for item in result.red_flags)
    else:
        lines.append("- 未发现明显营销红线")
    if result.hard_vetoes:
        lines.extend(f"- 硬性否决：{item}" for item in result.hard_vetoes)

    lines.append("")
    lines.append("## 证据核验")
    if result.evidence_checks:
        lines.extend(f"- {item.claim}：{item.status.value}（{item.note}）" for item in result.evidence_checks)
    else:
        lines.append("- 尚无证据核验结果")

    if result.timing:
        lines.append("")
        lines.append("## 时机判断")
        lines.append(f"- 状态：{result.timing.status.value}")
        lines.append(f"- 分数：{result.timing.score}")
        lines.extend(f"- {item}" for item in result.timing.notes)

    if result.technical:
        lines.append("")
        lines.append("## 技术面体检")
        lines.append(f"- 状态：{result.technical.status.value}")
        lines.append(f"- 分数：{result.technical.score}")
        lines.extend(f"- {item}" for item in result.technical.notes)
        if result.technical.metrics:
            metrics = "，".join(f"{key}: {value}" for key, value in result.technical.metrics.items())
            lines.append(f"- 指标：{metrics}")

    if result.risk_rewards:
        lines.append("")
        lines.append("## 盈亏比")
        for name, rr in result.risk_rewards.items():
            ratio = "-" if rr.ratio is None else f"{rr.ratio:.2f}"
            lines.append(
                f"- {name}: 买入 {rr.buy_price:.2f}，目标 {rr.target_price:.2f}，"
                f"止损 {rr.stop_loss:.2f}，上涨 {rr.upside_pct:.2f}%，"
                f"下跌 {rr.downside_pct:.2f}%，盈亏比 {ratio}"
            )

    if result.entry_plan:
        lines.append("")
        lines.append("## 入场计划")
        lines.append(f"- 是否允许真实入场：{'是' if result.entry_plan.allowed else '否'}")
        lines.append(f"- 价格条件：{result.entry_plan.price_zone}")
        lines.extend(f"- 条件：{item}" for item in result.entry_plan.conditions)
        lines.extend(f"- 警告：{item}" for item in result.entry_plan.warnings)

    if result.exit_plan:
        lines.append("")
        lines.append("## 止损止盈")
        lines.append(f"- 止损价：{_fmt_price(result.exit_plan.stop_loss)}")
        if result.exit_plan.take_profit:
            lines.append(f"- 止盈价：{', '.join(f'{item:.2f}' for item in result.exit_plan.take_profit)}")
        lines.extend(f"- 规则：{item}" for item in result.exit_plan.rules)

    lines.append("")
    lines.append("## 下一步")
    lines.extend(f"- {item}" for item in result.next_checks)
    if result.follow_up_tasks:
        lines.append("")
        lines.append("## 复盘任务")
        for task in result.follow_up_tasks:
            lines.append(f"- {task.due_date}：{task.instruction}")
    lines.append("")
    lines.append("说明：以上为风控分析和条件计划，不构成投资建议。")
    return "\n".join(lines)
