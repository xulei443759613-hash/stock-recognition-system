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


@dataclass
class GroupMessage:
    raw_text: str
    push_time: str | None = None
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
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConfig:
    min_risk_reward_ratio: float = 1.5
    small_test_position_cap: float = 0.05
    verified_position_cap: float = 0.10
    max_single_trade_loss_pct: float = 0.01
    late_push_time: str = "14:30"


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
    timing: TimingReview | None = None
    technical: TechnicalReview | None = None
    entry_plan: EntryPlan | None = None
    exit_plan: ExitPlan | None = None
    position_plan: PositionPlan | None = None
    follow_up_tasks: list[FollowUpTask] = field(default_factory=list)
    report: str = ""
