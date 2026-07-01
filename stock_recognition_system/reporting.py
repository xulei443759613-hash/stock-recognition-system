from __future__ import annotations

from .models import ReviewResult


def _fmt_price(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _append_key_prices(lines: list[str], result: ReviewResult) -> None:
    parsed = result.parsed
    if not parsed:
        return

    current_price = result.opportunity_review.current_price if result.opportunity_review else None
    if current_price is None and result.short_term_plan:
        current_price = result.short_term_plan.buy_price

    lines.append("")
    lines.append("## 关键价位")
    lines.append(f"- 消息时点/当前价：{_fmt_price(current_price)}")
    lines.append(f"- 入场区间：{_fmt_price(parsed.entry_low)} - {_fmt_price(parsed.entry_high)}")
    lines.append(f"- 目标止盈价：{_fmt_price(parsed.target_price)}")
    lines.append(f"- 硬止损价：{_fmt_price(parsed.stop_loss)}")

    if result.suggested_exit_plan:
        plan = result.suggested_exit_plan
        lines.append(f"- 系统建议止盈价：{_fmt_price(plan.suggested_take_profit)}")
        lines.append(f"- 系统建议止损价：{_fmt_price(plan.suggested_stop_loss)}")
        if plan.risk_reward_ratio is not None:
            lines.append(f"- 系统建议盈亏比：{plan.risk_reward_ratio:.2f}")

    if result.opportunity_review:
        review = result.opportunity_review
        if review.max_buy_price is not None:
            lines.append(f"- 普通风控最高买入价：{_fmt_price(review.max_buy_price)}")
        if review.executable_max_buy_price is not None:
            lines.append(f"- 训练模式综合可执行价：{_fmt_price(review.executable_max_buy_price)}")
        if review.required_pullback_pct is not None:
            lines.append(f"- 重新评估所需回撤：{review.required_pullback_pct:.2f}%")

    if result.short_term_plan:
        plan = result.short_term_plan
        lines.append(f"- 短线 5% 止盈价：{_fmt_price(plan.take_profit_5_pct)}")
        lines.append(f"- 短线 8% 止盈价：{_fmt_price(plan.take_profit_8_pct)}")
        lines.append(f"- 短线 10% 止盈价：{_fmt_price(plan.take_profit_10_pct)}")


def _append_training_plan(lines: list[str], result: ReviewResult) -> None:
    plan = result.training_plan
    if not plan:
        return

    lines.append("")
    lines.append("## 训练档位")
    lines.append(f"- 档位：{plan.label}")
    lines.append(f"- 是否允许真实 100 股：{'是' if plan.real_trade_allowed else '否'}")
    lines.append(f"- 最大训练股数：{plan.max_shares}")
    lines.append(f"- 参考买入价：{_fmt_price(plan.reference_buy_price)}")
    lines.append(f"- 综合建议止盈价：{_fmt_price(plan.suggested_take_profit)}")
    lines.append(f"- 综合建议止损价：{_fmt_price(plan.suggested_stop_loss)}")
    if plan.planned_cash is not None:
        lines.append(f"- 买 100 股预计占用：{plan.planned_cash:.2f}")
    if plan.planned_profit_cash is not None:
        lines.append(f"- 触发止盈预计盈利：{plan.planned_profit_cash:.2f}")
    if plan.planned_loss_cash is not None:
        lines.append(f"- 触发止损预计亏损：{plan.planned_loss_cash:.2f}")
    lines.extend(f"- 原因：{item}" for item in plan.reasons)
    lines.extend(f"- 执行清单：{item}" for item in plan.checklist)


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

    _append_key_prices(lines, result)
    _append_training_plan(lines, result)

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

    if result.evidence_requirements:
        lines.append("")
        lines.append("## 证据采集计划")
        for item in result.evidence_requirements:
            lines.append(f"- [{item.priority}] {item.claim}：{item.category}")
            if item.required_sources:
                lines.append(f"  - 来源：{'；'.join(item.required_sources)}")
            if item.collect:
                lines.append(f"  - 采集：{'；'.join(item.collect)}")
            if item.pass_criteria:
                lines.append(f"  - 通过：{'；'.join(item.pass_criteria)}")
            if item.reject_criteria:
                lines.append(f"  - 否决：{'；'.join(item.reject_criteria)}")
            if item.notes:
                lines.append(f"  - 备注：{'；'.join(item.notes)}")

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

    if result.opportunity_review:
        review = result.opportunity_review
        lines.append("")
        lines.append("## 机会评级")
        lines.append(f"- 评级：{review.rating}")
        lines.append(f"- 状态：{review.status}")
        lines.append(f"- 分数：{review.score}")
        lines.append(f"- 是否允许真实仓位：{'是' if review.real_trade_allowed else '否'}")
        if review.current_price is not None:
            lines.append(f"- 消息时点/当前价：{_fmt_price(review.current_price)}")
        if parsed:
            lines.append(f"- 目标止盈价：{_fmt_price(parsed.target_price)}")
            lines.append(f"- 硬止损价：{_fmt_price(parsed.stop_loss)}")
        if review.max_buy_price is not None:
            lines.append(f"- 普通风控最高买入价：{_fmt_price(review.max_buy_price)}")
        if review.short_term_max_buy_price is not None:
            lines.append(f"- 短线盈亏比最高买入价：{_fmt_price(review.short_term_max_buy_price)}")
        if review.one_lot_loss_max_buy_price is not None:
            lines.append(f"- 100 股止损风险最高买入价：{_fmt_price(review.one_lot_loss_max_buy_price)}")
        if review.executable_max_buy_price is not None:
            lines.append(f"- 训练模式综合可执行价：{_fmt_price(review.executable_max_buy_price)}")
        if review.required_pullback_pct is not None:
            lines.append(f"- 重新评估所需回撤：{review.required_pullback_pct:.2f}%")
        if result.short_term_plan:
            plan = result.short_term_plan
            lines.append(f"- 短线 5% 止盈价：{_fmt_price(plan.take_profit_5_pct)}")
            lines.append(f"- 短线 8% 止盈价：{_fmt_price(plan.take_profit_8_pct)}")
            lines.append(f"- 短线 10% 止盈价：{_fmt_price(plan.take_profit_10_pct)}")
        lines.extend(f"- 原因：{item}" for item in review.reasons)
        lines.extend(f"- 观察条件：{item}" for item in review.watch_conditions)
        lines.extend(f"- 复盘口径：{item}" for item in review.missed_review_rules)

    if result.suggested_exit_plan:
        plan = result.suggested_exit_plan
        lines.append("")
        lines.append("## 系统建议止盈止损")
        lines.append(f"- 参考买入价：{_fmt_price(plan.reference_buy_price)}")
        lines.append(f"- 建议止盈价：{_fmt_price(plan.suggested_take_profit)}")
        lines.append(f"- 建议止损价：{_fmt_price(plan.suggested_stop_loss)}")
        if plan.reward_pct is not None:
            lines.append(f"- 预期收益：{plan.reward_pct:.2f}%")
        if plan.risk_pct is not None:
            lines.append(f"- 预期风险：{plan.risk_pct:.2f}%")
        if plan.risk_reward_ratio is not None:
            lines.append(f"- 建议盈亏比：{plan.risk_reward_ratio:.2f}")
        if plan.max_loss_per_lot is not None:
            lines.append(f"- 买 100 股触发建议止损约亏：{plan.max_loss_per_lot:.2f}")
        lines.extend(f"- 依据：{item}" for item in plan.basis)
        lines.extend(f"- 提醒：{item}" for item in plan.warnings)

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

    if result.short_term_plan:
        plan = result.short_term_plan
        lines.append("")
        lines.append("## 4-5 日短线训练计划")
        lines.append(f"- 是否允许短线真实买入：{'是' if plan.allowed else '否'}")
        lines.append(f"- 账户金额：{plan.account_value:.2f}")
        lines.append(f"- 训练仓：{plan.training_bucket:.2f}")
        lines.append(f"- 单票现金上限：{plan.max_position_cash:.2f}")
        lines.append(f"- 单笔最大亏损：{plan.max_trade_loss_cash:.2f}")
        lines.append(f"- 参考买入价：{_fmt_price(plan.buy_price)}")
        if plan.min_lot_cash is not None:
            lines.append(f"- 买 100 股约需：{plan.min_lot_cash:.2f}")
        if plan.min_lot_risk_cash is not None:
            lines.append(f"- 买 100 股触发止损约亏：{plan.min_lot_risk_cash:.2f}")
        lines.append(f"- 最大股数：{plan.max_shares}")
        lines.append(f"- 预计占用资金：{plan.cash_needed:.2f}")
        lines.append(f"- 5% 止盈价：{_fmt_price(plan.take_profit_5_pct)}")
        lines.append(f"- 8% 止盈价：{_fmt_price(plan.take_profit_8_pct)}")
        lines.append(f"- 10% 止盈价：{_fmt_price(plan.take_profit_10_pct)}")
        lines.append(f"- 强制退出：{plan.exit_rule}")
        lines.extend(f"- 限制：{item}" for item in plan.reasons)

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
