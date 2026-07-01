from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalAction(str, Enum):
    ABANDON = "放弃"
    OBSERVE = "观察"
    WAIT_PULLBACK = "等待回踩"
    SIMULATE = "模拟盘"
    SMALL_TEST = "小仓位试错"
    HOLD_OBSERVE = "持有观察"
    TAKE_PROFIT = "分批止盈"
    STOP_EXIT = "止损/退出"


class EvidenceStatus(str, Enum):
    VERIFIED = "已验证"
    UNVERIFIED = "未验证"
    CONTRADICTED = "反向证据"
    NOT_APPLICABLE = "无法验证"


class TimingStatus(str, Enum):
    INVALID = "不可参与"
    WAIT = "等待条件"
    CAUTION = "谨慎观察"
    ACCEPTABLE = "条件合格"


class TechnicalStatus(str, Enum):
    WEAK = "走弱"
    NEUTRAL = "中性"
    HEALTHY = "健康"
    OVERHEATED = "过热"


class SourceTier(str, Enum):
    OFFICIAL_DISCLOSURE = "官方披露"
    EXCHANGE_MARKET_DATA = "交易所/行情数据"
    LICENSED_DATA_VENDOR = "合规数据供应商"
    REPUTABLE_MEDIA = "可信媒体"
    GROUP_MESSAGE = "群消息"
    UNKNOWN = "未知来源"


@dataclass
class GroupMessage:
    raw_text: str
    push_time: str | None = None
    push_date: str | None = None
    source: str = "group"


@dataclass
class ParsedSignal:
    stock_name: str | None = None
    stock_code: str | None = None
    entry_low: float | None = None
    entry_high: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    claimed_logic: list[str] = field(default_factory=list)
    adviser_text: str | None = None


@dataclass
class EvidenceCheck:
    claim: str
    status: EvidenceStatus
    note: str = ""


@dataclass
class EvidenceRequirement:
    claim: str
    category: str
    priority: str
    required_sources: list[str] = field(default_factory=list)
    collect: list[str] = field(default_factory=list)
    pass_criteria: list[str] = field(default_factory=list)
    reject_criteria: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class InformationSource:
    name: str
    tier: SourceTier
    url: str | None = None
    as_of: str | None = None
    note: str = ""


@dataclass
class TimingReview:
    status: TimingStatus
    score: int
    notes: list[str] = field(default_factory=list)


@dataclass
class TechnicalReview:
    status: TechnicalStatus
    score: int
    notes: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class EntryPlan:
    allowed: bool
    action: SignalAction
    price_zone: str
    conditions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    max_acceptable_buy_price: float | None = None


@dataclass
class ExitPlan:
    stop_loss: float | None
    take_profit: list[float] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)


@dataclass
class PositionPlan:
    max_position_pct: float
    max_loss_pct: float
    max_shares: int | None = None
    cash_needed: float | None = None
    note: str = ""


@dataclass
class ShortTermPlan:
    enabled: bool
    allowed: bool
    account_value: float
    training_bucket: float
    max_position_cash: float
    max_trade_loss_cash: float
    buy_price: float | None
    min_lot_shares: int
    min_lot_cash: float | None = None
    min_lot_risk_cash: float | None = None
    max_shares: int = 0
    cash_needed: float = 0.0
    stop_loss: float | None = None
    take_profit_5_pct: float | None = None
    take_profit_8_pct: float | None = None
    take_profit_10_pct: float | None = None
    max_holding_days: int = 5
    exit_rule: str = ""
    reasons: list[str] = field(default_factory=list)


@dataclass
class OpportunityReview:
    rating: str
    status: str
    score: int
    real_trade_allowed: bool
    current_price: float | None = None
    max_buy_price: float | None = None
    short_term_max_buy_price: float | None = None
    one_lot_loss_max_buy_price: float | None = None
    executable_max_buy_price: float | None = None
    required_pullback_pct: float | None = None
    reasons: list[str] = field(default_factory=list)
    watch_conditions: list[str] = field(default_factory=list)
    missed_review_rules: list[str] = field(default_factory=list)


@dataclass
class SuggestedExitPlan:
    reference_buy_price: float | None
    suggested_take_profit: float | None
    suggested_stop_loss: float | None
    reward_pct: float | None = None
    risk_pct: float | None = None
    risk_reward_ratio: float | None = None
    max_loss_per_lot: float | None = None
    basis: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TrainingTier(str, Enum):
    A_REAL_100 = "A档：可实盘100股"
    B_LIGHT_100 = "B档：轻仓训练100股"
    C_SIMULATE = "C档：模拟观察"
    D_ABANDON = "D档：放弃"


@dataclass
class TrainingPlan:
    tier: TrainingTier
    label: str
    real_trade_allowed: bool
    max_shares: int
    reference_buy_price: float | None = None
    suggested_take_profit: float | None = None
    suggested_stop_loss: float | None = None
    planned_cash: float | None = None
    planned_loss_cash: float | None = None
    planned_profit_cash: float | None = None
    reasons: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)


@dataclass
class FollowUpTask:
    stock_code: str | None
    stock_name: str | None
    source: str
    due_date: str
    task_type: str
    instruction: str
    status: str = "pending"


@dataclass
class MarketEvidence:
    current_price: float | None = None
    change_pct: float | None = None
    five_day_change_pct: float | None = None
    twenty_day_change_pct: float | None = None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    is_limit_up: bool | None = None
    market_index_change_pct: float | None = None
    sector_change_pct: float | None = None
    close_prices: list[float] = field(default_factory=list)
    board: str | None = None
    verified_claims: dict[str, bool] = field(default_factory=dict)
    evidence_notes: list[str] = field(default_factory=list)
    data_warnings: list[str] = field(default_factory=list)
    information_sources: list[InformationSource] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConfig:
    min_risk_reward_ratio: float = 1.5
    small_test_position_cap: float = 0.05
    verified_position_cap: float = 0.10
    max_single_trade_loss_pct: float = 0.01
    late_push_time: str = "14:30"
    default_account_value: float = 34000.0
    short_term_training_bucket_pct: float = 0.10
    short_term_position_cap: float = 0.10
    short_term_max_trade_loss_pct: float = 0.005
    short_term_min_risk_reward_ratio: float = 1.8
    board_lot_shares: int = 100
    short_term_max_holding_days: int = 5


@dataclass
class RiskReward:
    buy_price: float
    target_price: float
    stop_loss: float
    upside_pct: float
    downside_pct: float
    ratio: float | None


@dataclass
class ReviewResult:
    action: SignalAction
    confidence: int
    message_score: int
    evidence_score: int
    price_score: int
    beginner_score: int
    red_flags: list[str]
    hard_vetoes: list[str]
    risk_rewards: dict[str, RiskReward]
    max_position_pct: float
    reasons: list[str]
    next_checks: list[str]
    parsed: ParsedSignal | None = None
    evidence_checks: list[EvidenceCheck] = field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = field(default_factory=list)
    timing: TimingReview | None = None
    technical: TechnicalReview | None = None
    entry_plan: EntryPlan | None = None
    exit_plan: ExitPlan | None = None
    position_plan: PositionPlan | None = None
    short_term_plan: ShortTermPlan | None = None
    opportunity_review: OpportunityReview | None = None
    suggested_exit_plan: SuggestedExitPlan | None = None
    training_plan: TrainingPlan | None = None
    follow_up_tasks: list[FollowUpTask] = field(default_factory=list)
    report: str = ""
