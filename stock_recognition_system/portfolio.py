from __future__ import annotations

from dataclasses import dataclass, field

from .holdings import Holding
from .models import RiskConfig


@dataclass
class PortfolioRiskRow:
    holding_id: str
    stock_code: str
    stock_name: str | None
    shares: int
    buy_price: float
    current_price: float
    market_value: float
    planned_loss_cash: float | None
    planned_loss_pct: float | None


@dataclass
class PortfolioRiskReport:
    account_value: float
    holdings_count: int
    total_market_value: float
    total_planned_loss_cash: float
    exposure_pct: float
    planned_loss_pct: float
    rows: list[PortfolioRiskRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_portfolio_risk_report(
    holdings: list[Holding],
    current_prices: dict[str, float] | None = None,
    config: RiskConfig | None = None,
    account_value: float | None = None,
) -> PortfolioRiskReport:
    config = config or RiskConfig()
    account = account_value or config.default_account_value
    prices = current_prices or {}
    rows: list[PortfolioRiskRow] = []
    warnings: list[str] = []
    total_value = 0.0
    total_loss = 0.0

    for holding in holdings:
        current = prices.get(holding.stock_code, holding.buy_price)
        market_value = round(current * holding.shares, 2)
        planned_loss = None
        planned_loss_pct = None
        if holding.stop_loss is None:
            warnings.append(f"{holding.stock_code} 缺止损价，组合风险不可完整计算")
        else:
            planned_loss = round(max(0.0, current - holding.stop_loss) * holding.shares, 2)
            planned_loss_pct = round(planned_loss / account * 100, 2) if account > 0 else None
            total_loss += planned_loss
            if planned_loss / account > config.short_term_max_trade_loss_pct:
                warnings.append(
                    f"{holding.stock_code} 单票止损风险 {planned_loss:.2f} 超过训练单笔上限 "
                    f"{account * config.short_term_max_trade_loss_pct:.2f}"
                )

        total_value += market_value
        rows.append(
            PortfolioRiskRow(
                holding.id,
                holding.stock_code,
                holding.stock_name,
                holding.shares,
                holding.buy_price,
                current,
                market_value,
                planned_loss,
                planned_loss_pct,
            )
        )

    exposure_pct = round(total_value / account * 100, 2) if account > 0 else 0.0
    planned_loss_pct = round(total_loss / account * 100, 2) if account > 0 else 0.0
    if total_value / account > config.portfolio_max_position_pct:
        warnings.append(f"总持仓占用 {exposure_pct:.2f}% 超过新手组合上限 {config.portfolio_max_position_pct:.0%}")
    if total_loss / account > config.portfolio_max_loss_pct:
        warnings.append(f"组合止损风险 {planned_loss_pct:.2f}% 超过组合亏损上限 {config.portfolio_max_loss_pct:.0%}")
    if len(holdings) >= 4:
        warnings.append("同时持仓数量较多，新手短线阶段建议减少分散噪声")

    return PortfolioRiskReport(
        account,
        len(holdings),
        round(total_value, 2),
        round(total_loss, 2),
        exposure_pct,
        planned_loss_pct,
        rows,
        warnings,
    )
