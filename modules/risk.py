from dataclasses import dataclass
from typing import Protocol

from modules.strategy import StockAnalysis


class PortfolioConfigLike(Protocol):
    capital_nok: float
    max_positions: int
    position_sizing: str
    max_position_pct: float
    cash_reserve_pct: float


class RiskConfigLike(Protocol):
    stop_loss_pct: float
    take_profit_pct: float
    minimum_buy_score: int


class TradingConfigLike(Protocol):
    min_trade_size_nok: float
    min_score_for_buy: int


@dataclass(frozen=True)
class PortfolioRules:
    capital_nok: float
    max_positions: int
    position_sizing: str
    max_position_pct: float
    cash_reserve_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    minimum_buy_score: int
    min_position_size_nok: float = 0
    allow_leverage: bool = False
    allow_derivatives: bool = False
    allow_automatic_trading: bool = False

    @classmethod
    def from_config(cls, portfolio: PortfolioConfigLike, risk: RiskConfigLike, trading: TradingConfigLike | None = None) -> "PortfolioRules":
        return cls(
            capital_nok=portfolio.capital_nok,
            max_positions=portfolio.max_positions,
            position_sizing=portfolio.position_sizing,
            max_position_pct=portfolio.max_position_pct,
            cash_reserve_pct=portfolio.cash_reserve_pct,
            stop_loss_pct=risk.stop_loss_pct,
            take_profit_pct=risk.take_profit_pct,
            minimum_buy_score=trading.min_score_for_buy if trading else risk.minimum_buy_score,
            min_position_size_nok=trading.min_trade_size_nok if trading else 0,
        )


@dataclass(frozen=True)
class Allocation:
    ticker: str
    signal: str
    score: int
    suggested_amount_nok: float
    portfolio_weight: float
    entry_price: float
    stop_loss: float
    target_price: float
    risk_amount_nok: float
    reward_amount_nok: float
    expected_holding_period: str
    confidence_score: int
    note: str


def build_allocation_plan(
    analyses: list[StockAnalysis],
    rules: PortfolioRules,
) -> list[Allocation]:
    buy_candidates = [
        analysis
        for analysis in analyses
        if analysis.signal == "BUY" and analysis.score >= rules.minimum_buy_score
    ]
    buy_candidates.sort(key=lambda item: (item.score, item.confidence_score, -item.volatility), reverse=True)
    selected = buy_candidates[: rules.max_positions]

    if not selected:
        return []

    investable_capital = rules.capital_nok * (1 - rules.cash_reserve_pct)
    weights = calculate_position_weights(selected, rules.position_sizing)
    allocations = []
    max_position_amount = rules.capital_nok * rules.max_position_pct

    for analysis, weight in zip(selected, weights):
        suggested_amount = min(investable_capital * weight, max_position_amount)
        if suggested_amount < rules.min_position_size_nok:
            continue
        risk_amount = suggested_amount * rules.stop_loss_pct
        reward_amount = suggested_amount * rules.take_profit_pct
        allocations.append(Allocation(
            ticker=analysis.ticker,
            signal=analysis.signal,
            score=analysis.score,
            suggested_amount_nok=round(suggested_amount, 2),
            portfolio_weight=round(suggested_amount / rules.capital_nok, 4),
            entry_price=analysis.entry_price,
            stop_loss=analysis.stop_loss,
            target_price=analysis.target_price,
            risk_amount_nok=round(risk_amount, 2),
            reward_amount_nok=round(reward_amount, 2),
            expected_holding_period=analysis.expected_holding_period,
            confidence_score=analysis.confidence_score,
            note="Manual review required before any trade",
        ))

    return allocations


def calculate_position_weights(
    selected: list[StockAnalysis],
    position_sizing: str,
) -> list[float]:
    if position_sizing == "equal_weight":
        return [1 / len(selected) for _ in selected]

    if position_sizing == "risk_weighted":
        raw_weights = [max(0.01, analysis.confidence_score / max(analysis.volatility, 0.01)) for analysis in selected]
    else:
        raw_weights = [max(0.01, analysis.score) for analysis in selected]

    total = sum(raw_weights)
    return [weight / total for weight in raw_weights]
