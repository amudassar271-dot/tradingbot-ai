from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from modules.backtest import (
    BacktestResult,
    fetch_backtest_histories,
    get_trading_dates,
    run_momentum_portfolio_backtest,
)
from modules.benchmark import (
    BenchmarkResult,
    SimpleTicker,
    build_equal_weight_benchmark,
    build_single_asset_benchmark,
)
from modules.config import AppConfig


ROLLING_PERIODS = {
    "last_3_months": 63,
    "last_6_months": 126,
    "last_12_months": 252,
    "last_24_months": 504,
}
TOP_N_VALUES = [1, 2, 3, 5]
REBALANCE_VALUES = ["monthly", "quarterly"]
STOP_LOSS_VALUES = [0.08, 0.12, 0.15]
MOMENTUM_THRESHOLDS = [0.0, 0.05, 0.10]
COMPARISON_BENCHMARKS = ["QQQ", "SPY"]
STRESS_CAPITAL = 20_000


@dataclass(frozen=True)
class MomentumStressRow:
    period: str
    top_n: int
    rebalance: str
    stop_loss: float
    momentum_threshold: float
    net_return_pct: float
    maximum_drawdown_pct: float
    number_of_trades: int
    total_commissions: float
    ending_capital: float
    mode_name: str = "momentum_portfolio"
    category: str = "sensitivity"


def run_momentum_stress_test(watchlist, config: AppConfig) -> list[MomentumStressRow]:
    fetch_items = [*watchlist, *[SimpleTicker(ticker) for ticker in ["NVDA", "QQQ", "SPY"]]]
    histories = fetch_backtest_histories(fetch_items, config.backtest.history_period)
    period_histories = build_period_histories(histories)

    rows: list[MomentumStressRow] = []
    for period_name, sliced_histories in period_histories.items():
        analysis_cache = {}
        for top_n in TOP_N_VALUES:
            for rebalance in REBALANCE_VALUES:
                for stop_loss in STOP_LOSS_VALUES:
                    for threshold in MOMENTUM_THRESHOLDS:
                        result = run_momentum_portfolio_backtest(
                            watchlist,
                            sliced_histories,
                            config,
                            STRESS_CAPITAL,
                            top_n=top_n,
                            rebalance_frequency=rebalance,
                            stop_loss_pct=stop_loss,
                            minimum_momentum_threshold=threshold,
                            analysis_cache=analysis_cache,
                        )
                        rows.append(stress_row_from_result(
                            result,
                            period_name,
                            top_n,
                            rebalance,
                            stop_loss,
                            threshold,
                        ))

    comparison_histories = period_histories[max(period_histories, key=lambda name: ROLLING_PERIODS[name])]
    rows.extend(run_stress_comparison_rows(watchlist, comparison_histories, config))
    return rows


def build_period_histories(histories: dict[str, pd.DataFrame]) -> dict[str, dict[str, pd.DataFrame]]:
    trading_dates = get_trading_dates(histories)
    if not trading_dates:
        raise ValueError("No historical data available for momentum stress test")

    period_histories = {}
    for period_name, trading_day_count in ROLLING_PERIODS.items():
        if len(trading_dates) < 50:
            continue
        start_index = max(0, len(trading_dates) - trading_day_count)
        start_date = trading_dates[start_index]
        sliced = {
            ticker: history.loc[history.index >= start_date].copy()
            for ticker, history in histories.items()
            if not history.loc[history.index >= start_date].empty
        }
        if len(get_trading_dates(sliced)) >= 50:
            period_histories[period_name] = sliced
    return period_histories


def stress_row_from_result(
    result: BacktestResult,
    period: str,
    top_n: int,
    rebalance: str,
    stop_loss: float,
    momentum_threshold: float,
    category: str = "sensitivity",
) -> MomentumStressRow:
    return MomentumStressRow(
        period=period,
        top_n=top_n,
        rebalance=rebalance,
        stop_loss=stop_loss,
        momentum_threshold=momentum_threshold,
        net_return_pct=result.net_return_pct,
        maximum_drawdown_pct=result.maximum_drawdown_pct,
        number_of_trades=result.number_of_trades,
        total_commissions=result.total_commissions,
        ending_capital=result.ending_capital,
        mode_name=result.mode_name,
        category=category,
    )


def run_stress_comparison_rows(
    watchlist,
    histories: dict[str, pd.DataFrame],
    config: AppConfig,
) -> list[MomentumStressRow]:
    rows = []
    base = run_momentum_portfolio_backtest(
        watchlist,
        histories,
        config,
        STRESS_CAPITAL,
        mode_name="momentum_portfolio",
        analysis_cache={},
    )
    shared_no_nvda_cache = {}
    no_nvda = run_momentum_portfolio_backtest(
        watchlist,
        histories,
        config,
        STRESS_CAPITAL,
        exclude_tickers={"NVDA"},
        mode_name="momentum_portfolio_no_nvda",
        analysis_cache=shared_no_nvda_cache,
    )
    rows.append(stress_row_from_result(base, "comparison_24_months", 3, "monthly", config.risk.stop_loss_pct, 0.0, "comparison"))
    rows.append(stress_row_from_result(no_nvda, "comparison_24_months", 3, "monthly", config.risk.stop_loss_pct, 0.0, "comparison"))

    equal_weight = build_equal_weight_benchmark(watchlist, histories, STRESS_CAPITAL, config)
    if equal_weight:
        rows.append(stress_row_from_benchmark(equal_weight, "comparison_24_months"))
    for ticker in COMPARISON_BENCHMARKS:
        benchmark = build_single_asset_benchmark(f"Buy and hold {ticker}", ticker, histories, STRESS_CAPITAL, config)
        if benchmark:
            rows.append(stress_row_from_benchmark(benchmark, "comparison_24_months"))
    return rows


def stress_row_from_benchmark(result: BenchmarkResult, period: str) -> MomentumStressRow:
    return MomentumStressRow(
        period=period,
        top_n=0,
        rebalance="buy_hold",
        stop_loss=0,
        momentum_threshold=0,
        net_return_pct=result.net_return_pct,
        maximum_drawdown_pct=result.maximum_drawdown_pct,
        number_of_trades=result.number_of_trades,
        total_commissions=result.total_commissions,
        ending_capital=result.ending_capital,
        mode_name=result.name,
        category="comparison",
    )


def write_momentum_stress_test_report(rows: list[MomentumStressRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sensitivity_rows = [row for row in rows if row.category == "sensitivity"]
    comparison_rows = [row for row in rows if row.category == "comparison"]

    lines = [
        "# Momentum Stress Test Report",
        "",
        "This is a historical research simulation only. It is not financial advice.",
        f"Stress-test capital: {STRESS_CAPITAL:,.0f} NOK. Fixed Nordnet Mini commission: 29 NOK per trade.",
        "",
        "## Sensitivity Matrix",
        "",
        "| period | top_n | rebalance | stop_loss | momentum_threshold | net_return | max_drawdown | trades | commissions | ending_capital |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for row in sorted(sensitivity_rows, key=lambda item: (ROLLING_PERIODS.get(item.period, 0), item.top_n, item.rebalance, item.stop_loss, item.momentum_threshold)):
        lines.append(format_stress_row(row))

    lines.extend([
        "",
        "## Strategy And Benchmark Comparison",
        "",
        "| period | strategy | top_n | rebalance | stop_loss | momentum_threshold | net_return | max_drawdown | trades | commissions | ending_capital |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])

    for row in sorted(comparison_rows, key=lambda item: item.mode_name):
        lines.append(format_comparison_row(row))

    lines.extend([
        "",
        "## Interpretation",
        "",
        build_stress_interpretation(rows),
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def format_stress_row(row: MomentumStressRow) -> str:
    return (
        f"| {row.period} | {row.top_n} | {row.rebalance} | {row.stop_loss:.0%} | "
        f"{row.momentum_threshold:.0%} | {row.net_return_pct:.2%} | "
        f"{row.maximum_drawdown_pct:.2%} | {row.number_of_trades} | "
        f"{row.total_commissions:,.2f} NOK | {row.ending_capital:,.2f} NOK |"
    )


def format_comparison_row(row: MomentumStressRow) -> str:
    return (
        f"| {row.period} | {row.mode_name} | {row.top_n} | {row.rebalance} | "
        f"{row.stop_loss:.0%} | {row.momentum_threshold:.0%} | "
        f"{row.net_return_pct:.2%} | {row.maximum_drawdown_pct:.2%} | "
        f"{row.number_of_trades} | {row.total_commissions:,.2f} NOK | "
        f"{row.ending_capital:,.2f} NOK |"
    )


def build_stress_interpretation(rows: list[MomentumStressRow]) -> str:
    sensitivity_rows = [row for row in rows if row.category == "sensitivity"]
    comparison_rows = [row for row in rows if row.category == "comparison"]
    if not sensitivity_rows:
        return "No stress-test rows were generated."

    best_net = max(sensitivity_rows, key=lambda item: item.net_return_pct)
    best_risk_adjusted = max(sensitivity_rows, key=risk_adjusted_score)
    lowest_drawdown = max(sensitivity_rows, key=lambda item: item.maximum_drawdown_pct)
    base = next((row for row in comparison_rows if row.mode_name == "momentum_portfolio"), None)
    no_nvda = next((row for row in comparison_rows if row.mode_name == "momentum_portfolio_no_nvda"), None)

    lines = [
        "Best net return: "
        f"{describe_config(best_net)} with {best_net.net_return_pct:.2%} net return.",
        "Best risk-adjusted return: "
        f"{describe_config(best_risk_adjusted)} with score {risk_adjusted_score(best_risk_adjusted):.2f}.",
        "Lowest drawdown: "
        f"{describe_config(lowest_drawdown)} with {lowest_drawdown.maximum_drawdown_pct:.2%} max drawdown.",
    ]

    if base and no_nvda:
        dependency_gap = base.net_return_pct - no_nvda.net_return_pct
        if no_nvda.net_return_pct > 0:
            lines.append(
                f"NVDA dependency check: excluding NVDA still produced {no_nvda.net_return_pct:.2%} net return, "
                f"versus {base.net_return_pct:.2%} with NVDA included. The gap was {dependency_gap:.2%}."
            )
        else:
            lines.append(
                f"NVDA dependency check: excluding NVDA reduced the strategy to {no_nvda.net_return_pct:.2%} net return, "
                f"versus {base.net_return_pct:.2%} with NVDA included. This suggests meaningful dependence on NVDA or similar high-momentum winners."
            )

    for benchmark_name in ["Buy and hold QQQ", "Buy and hold SPY", "Equal-weight buy and hold watchlist"]:
        benchmark = next((row for row in comparison_rows if row.mode_name == benchmark_name), None)
        if base and benchmark:
            outcome = "beat" if base.net_return_pct > benchmark.net_return_pct else "did not beat"
            lines.append(
                f"Base momentum_portfolio {outcome} {benchmark_name}: "
                f"{base.net_return_pct:.2%} vs {benchmark.net_return_pct:.2%}."
            )

    return "\n\n".join(lines)


def risk_adjusted_score(row: MomentumStressRow) -> float:
    drawdown = abs(row.maximum_drawdown_pct)
    if drawdown == 0:
        return row.net_return_pct
    return row.net_return_pct / drawdown


def describe_config(row: MomentumStressRow) -> str:
    return (
        f"{row.period}, top_n={row.top_n}, {row.rebalance}, "
        f"stop_loss={row.stop_loss:.0%}, momentum_threshold={row.momentum_threshold:.0%}"
    )
