from dataclasses import dataclass
from pathlib import Path

from modules.backtest import (
    BacktestResult,
    build_strategy_modes,
    fetch_backtest_histories,
    run_backtest_with_histories,
    run_momentum_portfolio_backtest,
)
from modules.benchmark import (
    BenchmarkResult,
    SimpleTicker,
    build_equal_weight_benchmark,
    build_single_asset_benchmark,
)
from modules.config import AppConfig


PASSIVE_BENCHMARKS = ["NVDA", "SPY", "QQQ", "OBX.OL"]


@dataclass(frozen=True)
class MomentumReportRow:
    name: str
    capital: float
    gross_return_pct: float
    net_return_pct: float
    ending_capital: float
    total_commissions: float
    number_of_trades: int
    maximum_drawdown_pct: float
    category: str
    holdings: str = ""


def run_momentum_strategy_comparison(
    watchlist,
    config: AppConfig,
    capital_scenarios: list[float],
) -> list[MomentumReportRow]:
    fetch_items = [*watchlist, *[SimpleTicker(ticker) for ticker in PASSIVE_BENCHMARKS]]
    histories = fetch_backtest_histories(fetch_items, config.backtest.history_period)
    watchlist_tickers = {item.ticker for item in watchlist}
    watchlist_histories = {
        ticker: history for ticker, history in histories.items() if ticker in watchlist_tickers
    }

    rows: list[MomentumReportRow] = []
    for capital in capital_scenarios:
        bot_results = [
            run_backtest_with_histories(watchlist, watchlist_histories, config, mode, capital)
            for mode in build_strategy_modes(config)
        ]
        momentum_result = run_momentum_portfolio_backtest(watchlist, histories, config, capital)
        rows.extend(backtest_result_to_row(result, "existing_bot") for result in bot_results)
        rows.append(backtest_result_to_row(momentum_result, "momentum"))

        equal_weight = build_equal_weight_benchmark(watchlist, histories, capital, config)
        if equal_weight is not None:
            rows.append(benchmark_result_to_row(equal_weight))

        for ticker in PASSIVE_BENCHMARKS:
            benchmark = build_single_asset_benchmark(f"Buy and hold {ticker}", ticker, histories, capital, config)
            if benchmark is not None:
                rows.append(benchmark_result_to_row(benchmark))

    return rows


def backtest_result_to_row(result: BacktestResult, category: str) -> MomentumReportRow:
    return MomentumReportRow(
        name=result.mode_name,
        capital=result.starting_capital,
        gross_return_pct=result.gross_return_pct,
        net_return_pct=result.net_return_pct,
        ending_capital=result.ending_capital,
        total_commissions=result.total_commissions,
        number_of_trades=result.number_of_trades,
        maximum_drawdown_pct=result.maximum_drawdown_pct,
        category=category,
        holdings=format_holdings(result),
    )


def benchmark_result_to_row(result: BenchmarkResult) -> MomentumReportRow:
    return MomentumReportRow(
        name=result.name,
        capital=result.capital,
        gross_return_pct=result.gross_return_pct,
        net_return_pct=result.net_return_pct,
        ending_capital=result.ending_capital,
        total_commissions=result.total_commissions,
        number_of_trades=result.number_of_trades,
        maximum_drawdown_pct=result.maximum_drawdown_pct,
        category="benchmark",
    )


def format_holdings(result: BacktestResult) -> str:
    if not result.holdings:
        return "Cash only"
    return ", ".join(
        f"{holding.ticker} ({holding.shares:.2f} shares)"
        for holding in sorted(result.holdings, key=lambda item: item.ticker)
    )


def write_momentum_strategy_report(rows: list[MomentumReportRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Momentum Portfolio Strategy Report",
        "",
        "This is a historical research simulation only. It is not financial advice.",
        "The momentum portfolio is research-only and does not place trades.",
        "Fixed Nordnet Mini commission: 29 NOK per trade.",
        "",
        "| Strategy / Benchmark | Capital | Gross return | Net return after commission | Ending capital | Total commissions | Trades | Max drawdown |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for row in sorted(rows, key=lambda item: (item.capital, item.category, item.name)):
        lines.append(
            f"| {row.name} | {row.capital:,.0f} NOK | {row.gross_return_pct:.2%} | "
            f"{row.net_return_pct:.2%} | {row.ending_capital:,.2f} NOK | "
            f"{row.total_commissions:,.2f} NOK | {row.number_of_trades} | "
            f"{row.maximum_drawdown_pct:.2%} |"
        )

    lines.extend([
        "",
        "## Current Simulated Holdings",
        "",
        "| Capital | Strategy | Holdings |",
        "| ---: | --- | --- |",
    ])

    for row in sorted([item for item in rows if item.category in {"existing_bot", "momentum"}], key=lambda item: (item.capital, item.name)):
        lines.append(f"| {row.capital:,.0f} NOK | {row.name} | {row.holdings or 'Not applicable'} |")

    lines.extend([
        "",
        "## Interpretation",
        "",
        build_momentum_interpretation(rows),
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_momentum_interpretation(rows: list[MomentumReportRow]) -> str:
    if not rows:
        return "No momentum strategy results were generated."

    lines = []
    for capital in sorted({row.capital for row in rows}):
        capital_rows = [row for row in rows if row.capital == capital]
        momentum = next((row for row in capital_rows if row.name == "momentum_portfolio"), None)
        existing_bots = [row for row in capital_rows if row.category == "existing_bot"]
        equal_weight = next((row for row in capital_rows if row.name == "Equal-weight buy and hold watchlist"), None)
        spy = next((row for row in capital_rows if row.name == "Buy and hold SPY"), None)
        qqq = next((row for row in capital_rows if row.name == "Buy and hold QQQ"), None)
        nvda = next((row for row in capital_rows if row.name == "Buy and hold NVDA"), None)

        if momentum is None:
            continue

        best_existing = max(existing_bots, key=lambda item: item.net_return_pct) if existing_bots else None
        if best_existing:
            outcome = "beat" if momentum.net_return_pct > best_existing.net_return_pct else "did not beat"
            lines.append(
                f"For {capital:,.0f} NOK, momentum_portfolio {outcome} the best existing bot mode: "
                f"{momentum.net_return_pct:.2%} vs {best_existing.name} at {best_existing.net_return_pct:.2%}."
            )
        if equal_weight:
            outcome = "beat" if momentum.net_return_pct > equal_weight.net_return_pct else "did not beat"
            lines.append(
                f"For {capital:,.0f} NOK, momentum_portfolio {outcome} the equal-weight watchlist benchmark: "
                f"{momentum.net_return_pct:.2%} vs {equal_weight.net_return_pct:.2%}."
            )
        market_rows = [row for row in [spy, qqq] if row is not None]
        if market_rows:
            best_market = max(market_rows, key=lambda item: item.net_return_pct)
            outcome = "beat" if momentum.net_return_pct > best_market.net_return_pct else "did not beat"
            lines.append(
                f"For {capital:,.0f} NOK, momentum_portfolio {outcome} SPY/QQQ: "
                f"{momentum.net_return_pct:.2%} vs {best_market.name} at {best_market.net_return_pct:.2%}."
            )
        if nvda:
            outcome = "beat" if momentum.net_return_pct > nvda.net_return_pct else "did not beat"
            lines.append(
                f"For {capital:,.0f} NOK, momentum_portfolio {outcome} NVDA buy and hold: "
                f"{momentum.net_return_pct:.2%} vs {nvda.net_return_pct:.2%}."
            )

        if momentum.net_return_pct > 0:
            risk_note = (
                "but the drawdown is high and would need risk controls before treating it as robust"
                if momentum.maximum_drawdown_pct <= -0.25
                else "with acceptable drawdown in this test window"
            )
            lines.append(
                f"For {capital:,.0f} NOK, momentum_portfolio was economically viable after commission in this historical window, "
                f"{risk_note}: {momentum.net_return_pct:.2%} net return, {momentum.maximum_drawdown_pct:.2%} max drawdown, "
                f"and {momentum.number_of_trades} trades."
            )
        else:
            lines.append(
                f"For {capital:,.0f} NOK, momentum_portfolio was not viable in this historical window: "
                f"{momentum.net_return_pct:.2%} net return, {momentum.maximum_drawdown_pct:.2%} max drawdown, "
                f"and {momentum.number_of_trades} trades."
            )

    return "\n\n".join(lines)
