from __future__ import annotations

from .models import EvidenceCheck, EvidenceStatus, MarketEvidence, ParsedSignal, RiskConfig, TimingReview, TimingStatus


SEVERE_KEYWORDS = ["必涨", "稳赚", "包赚", "内幕", "马上拉升", "不买后悔", "最后机会", "保本", "翻倍"]
MEDIUM_KEYWORDS = ["金股", "控盘", "游资", "高控盘", "资金热度", "困境反转", "涨价", "主力", "抢筹", "低位启动"]


def detect_red_flags(parsed: ParsedSignal, raw_text: str, push_time: str | None) -> list[str]:
    flags: list[str] = []
    for keyword in SEVERE_KEYWORDS:
        if keyword in raw_text:
            flags.append(f"严重话术：{keyword}")
    for keyword in MEDIUM_KEYWORDS:
        if keyword in raw_text:
            flags.append(f"风险话术：{keyword}")
    if "不构成投资建议" in raw_text and parsed.entry_low is not None and parsed.target_price is not None:
        flags.append("给出入场/目标/止损，同时声明不构成建议，存在话术矛盾")
    if "服务团队" in raw_text or "咨询公司" in raw_text:
        flags.append("引导咨询服务团队，可能存在投顾转化话术")
    if push_time and push_time[-5:] >= "14:30":
        flags.append("14:30 后推送，验证时间不足")
    return flags


def hard_vetoes(parsed: ParsedSignal, evidence: MarketEvidence, config: RiskConfig) -> list[str]:
    vetoes: list[str] = []
    if evidence.current_price is None:
        vetoes.append("缺当前价，不能输出可执行动作")
    if parsed.stop_loss is None or parsed.target_price is None:
        vetoes.append("缺目标价或止损价")
    if parsed.stop_loss is not None and parsed.target_price is not None and parsed.target_price <= parsed.stop_loss:
        vetoes.append("目标价不高于止损价，价格结构无效")
    if parsed.entry_high is not None and parsed.stop_loss is not None and parsed.stop_loss >= parsed.entry_high:
        vetoes.append("止损价无效")
    if evidence.current_price is not None and parsed.stop_loss is not None and evidence.current_price <= parsed.stop_loss:
        vetoes.append("当前价已到或跌破止损价")
    if evidence.current_price is not None and parsed.target_price is not None and evidence.current_price > parsed.target_price:
        vetoes.append("当前价已超过目标价，未买者不追")
    if evidence.is_limit_up:
        vetoes.append("已涨停或接近涨停，未买者不追")
    return vetoes


def _claim_value(claim: str, verified_claims: dict[str, bool]) -> bool | None:
    if claim in verified_claims:
        return verified_claims[claim]
    for key, value in verified_claims.items():
        if claim in key or key in claim:
            return value
    return None


def verify_claims(parsed: ParsedSignal, evidence: MarketEvidence) -> list[EvidenceCheck]:
    if not parsed.claimed_logic:
        return [EvidenceCheck("推荐逻辑", EvidenceStatus.NOT_APPLICABLE, "消息未提供可核验逻辑")]

    checks: list[EvidenceCheck] = []
    for claim in parsed.claimed_logic:
        value = _claim_value(claim, evidence.verified_claims)
        if value is True:
            checks.append(EvidenceCheck(claim, EvidenceStatus.VERIFIED, "外部证据支持"))
        elif value is False:
            checks.append(EvidenceCheck(claim, EvidenceStatus.CONTRADICTED, "外部证据不支持或相反"))
        else:
            checks.append(EvidenceCheck(claim, EvidenceStatus.UNVERIFIED, "尚未接入或尚未核验"))
    return checks


def review_timing(parsed: ParsedSignal, evidence: MarketEvidence, push_time: str | None, config: RiskConfig) -> TimingReview:
    score = 70
    notes: list[str] = []
    status = TimingStatus.ACCEPTABLE

    if evidence.current_price is None:
        return TimingReview(TimingStatus.WAIT, 30, ["缺当前价，只能做条件分析"])

    if parsed.target_price is not None and evidence.current_price > parsed.target_price:
        return TimingReview(TimingStatus.INVALID, 0, ["当前价已超过目标价"])

    if evidence.is_limit_up:
        return TimingReview(TimingStatus.INVALID, 0, ["涨停或接近涨停，不追"])

    if parsed.stop_loss is not None and evidence.current_price <= parsed.stop_loss:
        return TimingReview(TimingStatus.INVALID, 0, ["当前价已到或跌破止损价"])

    if parsed.entry_high is not None and evidence.current_price > parsed.entry_high:
        score -= 35
        status = TimingStatus.WAIT
        notes.append("当前价高于入场上沿，等待回踩")

    if parsed.entry_low is not None and evidence.current_price < parsed.entry_low:
        score -= 10
        status = TimingStatus.CAUTION
        notes.append("当前价低于入场区间，先确认是否走弱")

    if push_time and push_time[-5:] >= config.late_push_time:
        score -= 15
        status = TimingStatus.CAUTION if status == TimingStatus.ACCEPTABLE else status
        notes.append("尾盘推送，次日确认优先")

    if evidence.five_day_change_pct is not None and evidence.five_day_change_pct >= 15:
        score -= 20
        status = TimingStatus.CAUTION if status == TimingStatus.ACCEPTABLE else status
        notes.append("5 日涨幅较大，追高风险上升")

    if evidence.market_index_change_pct is not None and evidence.market_index_change_pct <= -1.5:
        score -= 10
        status = TimingStatus.CAUTION if status == TimingStatus.ACCEPTABLE else status
        notes.append("大盘弱势，降低执行优先级")

    if evidence.sector_change_pct is not None and evidence.sector_change_pct <= -2:
        score -= 10
        status = TimingStatus.CAUTION if status == TimingStatus.ACCEPTABLE else status
        notes.append("板块弱势，降低执行优先级")

    if not notes:
        notes.append("价格位置未触发明显时机否决")

    return TimingReview(status, max(0, min(100, score)), notes)


def score_message(red_flags: list[str]) -> int:
    score = 80
    for flag in red_flags:
        score -= 15 if flag.startswith("严重") else 8
    return max(0, min(100, score))


def score_evidence(parsed: ParsedSignal, evidence: MarketEvidence, checks: list[EvidenceCheck] | None = None) -> int:
    checks = checks if checks is not None else verify_claims(parsed, evidence)
    if not parsed.claimed_logic:
        return 40
    if not evidence.verified_claims:
        return 35
    verified = sum(1 for item in checks if item.status == EvidenceStatus.VERIFIED)
    contradicted = sum(1 for item in checks if item.status == EvidenceStatus.CONTRADICTED)
    score = 35 + int(65 * verified / max(1, len(parsed.claimed_logic))) - contradicted * 20
    return max(0, min(100, score))
