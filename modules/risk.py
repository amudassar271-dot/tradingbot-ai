from dataclasses import dataclass

from modules.strategy import StockAnalysis


@dataclass(frozen=True)
class PortfolioRules:
    portfolio_size_nok: float
    max_positions: int
    allow_leverage: bool = False
    allow_derivatives: bool = False
    allow_automatic_trading: bool = False


@dataclass(frozen=True)
class Allocation:
    ticker: str
    signal: str
    suggested_amount_nok: float
    note: str


def build_allocation_plan(
    analyses: list[StockAnalysis],
    rules: PortfolioRules,
) -> list[Allocation]:
    buy_candidates = [
        analysis
        for analysis in analyses
        if analysis.signal == "BUY"
    ]
    buy_candidates.sort(key=lambda item: (item.momentum_30d, -item.volatility), reverse=True)
    selected = buy_candidates[: rules.max_positions]

    if not selected:
        return []

    amount_per_position = rules.portfolio_size_nok / len(selected)
    return [
        Allocation(
            ticker=analysis.ticker,
            signal=analysis.signal,
            suggested_amount_nok=round(amount_per_position, 2),
            note="Manual review required before any trade",
        )
        for analysis in selected
    ]
