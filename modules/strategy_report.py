from dataclasses import dataclass
from pathlib import Path

from modules.backtest import MomentumRank, fetch_backtest_histories, get_trading_dates, rank_momentum_universe
from modules.benchmark import SimpleTicker
from modules.config import AppConfig


@dataclass(frozen=True)
class StrategyCandidate:
    ticker: str
    name: str
    market: str
    rank: int
    allocation_nok: float
    entry_price: float
    stop_loss: float
    momentum_score: float
    momentum_30d: float
    momentum_90d: float | None
    relative_strength: float | None
    reason: str


@dataclass(frozen=True)
class PrimaryStrategyReport:
    strategy_name: str
    capital_nok: float
    top_n: int
    rebalance_frequency: str
    stop_loss_pct: float
    momentum_threshold_pct: float
    commission_nok: float
    candidates: list[StrategyCandidate]
    cash_reserve_nok: float
    replacement_note: str


def build_primary_strategy_report(watchlist, config: AppConfig) -> PrimaryStrategyReport:
    fetch_items = [*watchlist, SimpleTicker("QQQ"), SimpleTicker("SPY")]
    histories = fetch_backtest_histories(fetch_items, config.backtest.history_period)
    trading_dates = get_trading_dates({item.ticker: histories[item.ticker] for item in watchlist if item.ticker in histories})
    if not trading_dates:
        raise ValueError("No historical data available for primary strategy report")

    current_date = trading_dates[-1]
    rankings = rank_momentum_universe(watchlist, histories, current_date, config)
    qualified = [
        ranking for ranking in rankings
        if ranking.analysis.momentum_30d >= config.primary_strategy.momentum_threshold_pct
    ]
    selected = qualified[:config.primary_strategy.top_n]
    total_commissions = len(selected) * config.transaction_costs.fixed_nok
    investable_capital = max(0, config.primary_strategy.capital_nok - total_commissions)
    allocation_nok = investable_capital / config.primary_strategy.top_n if selected else 0

    candidates = [
        build_strategy_candidate(
            ranking=ranking,
            rank=index + 1,
            allocation_nok=allocation_nok,
            stop_loss_pct=config.primary_strategy.stop_loss_pct,
        )
        for index, ranking in enumerate(selected)
    ]
    invested = allocation_nok * len(candidates)
    cash_reserve = config.primary_strategy.capital_nok - invested - total_commissions

    return PrimaryStrategyReport(
        strategy_name=config.primary_strategy.name,
        capital_nok=config.primary_strategy.capital_nok,
        top_n=config.primary_strategy.top_n,
        rebalance_frequency=config.primary_strategy.rebalance_frequency,
        stop_loss_pct=config.primary_strategy.stop_loss_pct,
        momentum_threshold_pct=config.primary_strategy.momentum_threshold_pct,
        commission_nok=config.transaction_costs.fixed_nok,
        candidates=candidates,
        cash_reserve_nok=max(0, cash_reserve),
        replacement_note=build_replacement_note(candidates),
    )


def build_strategy_candidate(
    ranking: MomentumRank,
    rank: int,
    allocation_nok: float,
    stop_loss_pct: float,
) -> StrategyCandidate:
    analysis = ranking.analysis
    return StrategyCandidate(
        ticker=analysis.ticker,
        name=analysis.name,
        market=analysis.market,
        rank=rank,
        allocation_nok=allocation_nok,
        entry_price=analysis.close,
        stop_loss=analysis.close * (1 - stop_loss_pct),
        momentum_score=ranking.strength,
        momentum_30d=analysis.momentum_30d,
        momentum_90d=ranking.momentum_90d,
        relative_strength=ranking.relative_strength,
        reason=build_selection_reason(ranking),
    )


def build_selection_reason(ranking: MomentumRank) -> str:
    analysis = ranking.analysis
    reasons = []
    if analysis.close > analysis.sma50:
        reasons.append("price is above SMA50")
    if analysis.sma20 > analysis.sma50:
        reasons.append("SMA20 is above SMA50")
    if analysis.momentum_30d > 0:
        reasons.append(f"30-day momentum is {analysis.momentum_30d:.2%}")
    if ranking.momentum_90d is not None and ranking.momentum_90d > 0:
        reasons.append(f"90-day momentum is {ranking.momentum_90d:.2%}")
    if ranking.relative_strength is not None and ranking.relative_strength > 0:
        reasons.append("relative strength is better than QQQ/SPY")
    if not reasons:
        return "Selected by ranking, but confirmation is weak."
    return "; ".join(reasons) + "."


def build_replacement_note(candidates: list[StrategyCandidate]) -> str:
    if not candidates:
        return "No qualified momentum candidates. Existing discretionary holdings should be reviewed manually; the model suggests holding cash until momentum improves."
    tickers = ", ".join(candidate.ticker for candidate in candidates)
    return (
        f"Keep or open only the current top momentum candidates: {tickers}. "
        "Any manually held stock outside this list should be reviewed for replacement at the next manual rebalance."
    )


def write_strategy_report(report: PrimaryStrategyReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Primary Strategy Report",
        "",
        "Research-only momentum portfolio report. This does not place trades.",
        "",
        "## Strategy Settings",
        "",
        f"- Strategy: {report.strategy_name}",
        f"- Capital: {report.capital_nok:,.2f} NOK",
        f"- Positions: top {report.top_n}",
        f"- Rebalance: {report.rebalance_frequency}",
        f"- Stop loss: {report.stop_loss_pct:.0%}",
        f"- Minimum 30-day momentum: {report.momentum_threshold_pct:.0%}",
        f"- Commission assumption: {report.commission_nok:,.2f} NOK per trade",
        "",
        "## Current Top Momentum Candidates",
        "",
    ]

    if report.candidates:
        lines.extend([
            "| Rank | Ticker | Name | Market | Suggested allocation | Entry price | Stop loss | Momentum score | 30D momentum | 90D momentum | Relative strength | Reason for selection |",
            "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ])
        for candidate in report.candidates:
            lines.append(
                f"| {candidate.rank} | {candidate.ticker} | {candidate.name} | {candidate.market} | "
                f"{candidate.allocation_nok:,.2f} NOK | {candidate.entry_price:,.2f} | "
                f"{candidate.stop_loss:,.2f} | {candidate.momentum_score:.2f} | "
                f"{candidate.momentum_30d:.2%} | {format_optional_pct(candidate.momentum_90d)} | "
                f"{format_optional_pct(candidate.relative_strength)} | {candidate.reason} |"
            )
    else:
        lines.append("No stocks passed the configured momentum threshold.")

    lines.extend([
        "",
        "## Portfolio Action",
        "",
        f"- Current cash reserve after suggested buys and commission: {report.cash_reserve_nok:,.2f} NOK",
        f"- Keep or replace: {report.replacement_note}",
        "",
        "## Human decision required",
        "",
        "- This is not automatic trading.",
        "- You must manually approve and place any trades in Nordnet.",
        "- News and AI are context only and do not create trade orders.",
        "",
        "## Why these stocks?",
        "",
        build_plain_language_explanation(report),
        "",
        "## Risk Warning",
        "",
        "Momentum can reverse quickly. A strong trend today can become weak after earnings, macro news, or broad market selling. "
        "The stop loss is a research risk level, not a guaranteed exit price, and real market fills can be worse.",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_plain_language_explanation(report: PrimaryStrategyReport) -> str:
    if not report.candidates:
        return (
            "Ingen aksjer har sterk nok momentum akkurat na. Pa enkel norsk betyr det at modellen ikke ser nok trend, fart og relativ styrke til a foresla nye kjop."
        )

    tickers = ", ".join(candidate.ticker for candidate in report.candidates)
    return (
        f"Modellen velger {tickers} fordi de rangerer best pa trend, momentum og relativ styrke. "
        "Trend betyr at kursen ligger over et viktig gjennomsnitt, SMA50. "
        "Momentum betyr at aksjen har hatt tydelig positiv fart den siste tiden, spesielt siste 30 dager og helst ogsa rundt 90 dager. "
        "Relativ styrke betyr at aksjen prover a gjore det bedre enn brede alternativer som QQQ eller SPY. "
        "Risikoen styres med faerre posisjoner, lik fordeling og en 15% stop loss, men dette fjerner ikke risikoen for tap."
    )


def format_optional_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"
