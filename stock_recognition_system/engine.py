from __future__ import annotations

from .followup import build_follow_up_tasks
from .models import EntryPlan, EvidenceStatus, GroupMessage, MarketEvidence, ReviewResult, RiskConfig, SignalAction
from .parser import parse_group_message
from .reporting import build_markdown_report
from .risk import build_exit_plan, build_position_plan, calculate_risk_reward
from .rules import detect_red_flags, hard_vetoes, review_timing, score_evidence, score_message, verify_claims
from .technical import review_technical


class StockRecognitionEngine:
    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

    def review(
        self,
        message: GroupMessage,
        evidence: MarketEvidence | None = None,
        account_value: float | None = None,
    ) -> ReviewResult:
        evidence = evidence or MarketEvidence()
        parsed = parse_group_message(message)
        flags = detect_red_flags(parsed, message.raw_text, message.push_time)
        vetoes = hard_vetoes(parsed, evidence, self.config)
        evidence_checks = verify_claims(parsed, evidence)
        timing = review_timing(parsed, evidence, message.push_time, self.config)
        technical = review_technical(parsed, evidence)
        risk_rewards = {}

        if parsed.target_price is not None and parsed.stop_loss is not None:
            if parsed.entry_low is not None:
                risk_rewards["entry_low"] = calculate_risk_reward(parsed.entry_low, parsed.target_price, parsed.stop_loss)
            if parsed.entry_high is not None:
                risk_rewards["entry_high"] = calculate_risk_reward(parsed.entry_high, parsed.target_price, parsed.stop_loss)
            if evidence.current_price is not None:
                risk_rewards["current_price"] = calculate_risk_reward(evidence.current_price, parsed.target_price, parsed.stop_loss)

        message_score = score_message(flags)
        evidence_score = score_evidence(parsed, evidence, evidence_checks)
        price_score = min(self._score_price(parsed, evidence, risk_rewards), timing.score, technical.score)
        beginner_score = min(message_score, evidence_score, price_score)

        action = self._decide(vetoes, risk_rewards, evidence, parsed, beginner_score, evidence_checks)
        entry_plan = self._entry_plan(action, parsed, evidence, risk_rewards, evidence_checks)
        exit_plan = build_exit_plan(parsed)
        position_plan = build_position_plan(action, parsed, evidence.current_price, self.config, account_value)
        max_position = position_plan.max_position_pct
        confidence = int((message_score + evidence_score + price_score + beginner_score) / 4)

        rr_for_decision = risk_rewards.get("current_price") or risk_rewards.get("entry_low")
        reasons = flags + vetoes + [
            f"证据反向：{item.claim}" for item in evidence_checks if item.status == EvidenceStatus.CONTRADICTED
        ]
        if rr_for_decision and rr_for_decision.ratio is not None and rr_for_decision.ratio < self.config.min_risk_reward_ratio:
            reasons.append(f"盈亏比不足：{rr_for_decision.ratio:.2f} < {self.config.min_risk_reward_ratio}")
        if technical.score <= 35:
            reasons.append(f"技术面偏弱：{technical.status.value}")
        if not reasons:
            reasons.append("未发现硬性否决项，但仍需官方证据和当前价格确认")

        next_checks = ["核验公告/财报/调研记录", "记录次日表现", "记录5日表现"]
        if evidence.data_warnings:
            next_checks.extend(evidence.data_warnings)
        if any(item.status == EvidenceStatus.UNVERIFIED for item in evidence_checks):
            next_checks.append("补充未验证推荐逻辑的官方或行情证据")

        result = ReviewResult(
            action=action,
            confidence=confidence,
            message_score=message_score,
            evidence_score=evidence_score,
            price_score=price_score,
            beginner_score=beginner_score,
            red_flags=flags,
            hard_vetoes=vetoes,
            risk_rewards=risk_rewards,
            max_position_pct=max_position,
            reasons=reasons,
            next_checks=next_checks,
            parsed=parsed,
            evidence_checks=evidence_checks,
            timing=timing,
            technical=technical,
            entry_plan=entry_plan,
            exit_plan=exit_plan,
            position_plan=position_plan,
        )
        result.follow_up_tasks = build_follow_up_tasks(result)
        result.report = build_markdown_report(result)
        return result

    def _score_price(self, parsed, evidence: MarketEvidence, risk_rewards: dict) -> int:
        if evidence.current_price is None:
            return 30
        if parsed.target_price is not None and evidence.current_price > parsed.target_price:
            return 0
        if parsed.entry_high is not None and evidence.current_price > parsed.entry_high:
            return 35
        rr = risk_rewards.get("current_price") or risk_rewards.get("entry_low")
        if rr and rr.ratio is not None:
            if rr.ratio < self.config.min_risk_reward_ratio:
                return 30
            if rr.ratio < 2:
                return 55
        return 70

    def _decide(self, vetoes, risk_rewards, evidence, parsed, beginner_score: int, evidence_checks) -> SignalAction:
        if any("超过目标价" in item or "涨停" in item or "跌破止损价" in item for item in vetoes):
            return SignalAction.ABANDON
        if any("价格结构无效" in item or "止损价无效" in item for item in vetoes):
            return SignalAction.ABANDON
        if any("缺当前价" in item for item in vetoes):
            return SignalAction.OBSERVE
        if any("缺目标价或止损价" in item for item in vetoes):
            return SignalAction.OBSERVE
        rr = risk_rewards.get("current_price") or risk_rewards.get("entry_low")
        if rr and rr.ratio is not None and rr.ratio < self.config.min_risk_reward_ratio:
            return SignalAction.ABANDON
        if any(item.status == EvidenceStatus.CONTRADICTED for item in evidence_checks):
            return SignalAction.OBSERVE
        if evidence.current_price is not None and parsed.entry_high is not None and evidence.current_price > parsed.entry_high:
            return SignalAction.WAIT_PULLBACK
        if beginner_score < 50:
            return SignalAction.OBSERVE
        if beginner_score < 70:
            return SignalAction.SIMULATE
        return SignalAction.SMALL_TEST

    def _entry_plan(self, action, parsed, evidence: MarketEvidence, risk_rewards: dict, evidence_checks) -> EntryPlan:
        rr = risk_rewards.get("current_price") or risk_rewards.get("entry_low")
        conditions = [
            "当前价必须可核验",
            f"盈亏比不低于 {self.config.min_risk_reward_ratio}",
            "止损价有效且必须预先接受",
        ]
        warnings = [f"{item.claim} 尚未验证" for item in evidence_checks if item.status == EvidenceStatus.UNVERIFIED]

        if action == SignalAction.ABANDON:
            return EntryPlan(False, action, "不可入场", conditions, warnings + ["当前结论为放弃"])
        if action == SignalAction.OBSERVE:
            return EntryPlan(False, action, "只观察，不做真实仓位", conditions, warnings)
        if action == SignalAction.WAIT_PULLBACK:
            price_zone = "等待回到入场上沿以内"
            if parsed.entry_low is not None and parsed.entry_high is not None:
                price_zone = f"等待回到 {parsed.entry_low:.2f}-{parsed.entry_high:.2f}"
            return EntryPlan(False, action, price_zone, conditions, warnings)
        if action == SignalAction.SIMULATE:
            return EntryPlan(False, action, "仅模拟盘记录", conditions, warnings)

        price_zone = "当前价或入场区间"
        if evidence.current_price is not None:
            price_zone = f"当前价 {evidence.current_price:.2f} 附近，小仓试错"
        elif parsed.entry_low is not None and parsed.entry_high is not None:
            price_zone = f"{parsed.entry_low:.2f}-{parsed.entry_high:.2f}"
        if rr and rr.ratio is not None:
            conditions.append(f"当前盈亏比 {rr.ratio:.2f}")
        return EntryPlan(True, action, price_zone, conditions, warnings)

    def _position_cap(self, action: SignalAction) -> float:
        if action in {SignalAction.ABANDON, SignalAction.OBSERVE, SignalAction.WAIT_PULLBACK, SignalAction.SIMULATE}:
            return 0.0
        if action == SignalAction.SMALL_TEST:
            return self.config.small_test_position_cap
        return self.config.verified_position_cap
