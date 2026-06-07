from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from modules.backtest import BacktestResult, fetch_backtest_histories
from modules.config import AppConfig


SINGLE_STOCK_BENCHMARKS = ["AAPL", "MSFT", "NVDA", "DNB.OL", "EQNR.OL"]
MARKET_PROXY_CANDIDATES = {
    "S&P 500 proxy: SPY": ["SPY"],
    "Nasdaq proxy: QQQ": ["QQQ"],
    "Oslo Bors proxy": ["OBX.OL", "EUNL.OL"],
}


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    capital: float
    gross_return_pct: float
    net_return_pct: float
    ending_capital: float
    maximum_drawdown_pct: float
    number_of_trades: int
    total_commissions: float
    category: str


def run_benchmark_comparison(
    watchlist,
    config: AppConfig,
    capital_scenarios: list[float],
    bot_results: list[BacktestResult],
) -> list[BenchmarkResult]:
    tickers = sorted(set(SINGLE_STOCK_BENCHMARKS + ["SPY", "QQQ", "OBX.OL", "EUNL.OL"] + [item.ticker for item in watchlist]))
    histories = fetch_backtest_histories([SimpleTicker(ticker) for ticker in tickers], config.backtest.history_period)
    results = []

    for capital in capital_scenarios:
        results.extend(convert_bot_results(bot_results, capital))
        for ticker in SINGLE_STOCK_BENCHMARKS:
            result = build_single_asset_benchmark(f"Buy and hold {ticker}", ticker, histories, capital, config)
            if result:
                results.append(result)

        equal_weight = build_equal_weight_benchmark(watchlist, histories, capital, config)
        if equal_weight:
            results.append(equal_weight)

        for name, candidates in MARKET_PROXY_CANDIDATES.items():
            result = build_first_available_proxy(name, candidates, histories, capital, config)
            if result:
                results.append(result)

    return results


@dataclass(frozen=True)
class SimpleTicker:
    ticker: str
    name: str = ""
    market: str = ""


def convert_bot_results(bot_results: list[BacktestResult], capital: float) -> list[BenchmarkResult]:
    return [
        BenchmarkResult(
            name=f"Bot: {result.mode_name}",
            capital=result.starting_capital,
            gross_return_pct=result.gross_return_pct,
            net_return_pct=result.net_return_pct,
            ending_capital=result.ending_capital,
            maximum_drawdown_pct=result.maximum_drawdown_pct,
            number_of_trades=result.number_of_trades,
            total_commissions=result.total_commissions,
            category="bot",
        )
        for result in bot_results
        if result.starting_capital == capital
    ]


def build_first_available_proxy(
    name: str,
    candidates: list[str],
    histories: dict[str, pd.DataFrame],
    capital: float,
    config: AppConfig,
) -> BenchmarkResult | None:
    for ticker in candidates:
        if ticker in histories:
            return build_single_asset_benchmark(f"{name} ({ticker})", ticker, histories, capital, config)
    return None


def build_single_asset_benchmark(
    name: str,
    ticker: str,
    histories: dict[str, pd.DataFrame],
    capital: float,
    config: AppConfig,
) -> BenchmarkResult | None:
    history = histories.get(ticker)
    if history is None or history.empty:
        return None

    prices = history["Close"].dropna()
    if len(prices) < 2:
        return None

    buy_commission = config.transaction_costs.fixed_nok
    sell_commission = config.transaction_costs.fixed_nok
    shares = max(0, capital - buy_commission) / float(prices.iloc[0])
    gross_ending_capital = capital * (float(prices.iloc[-1]) / float(prices.iloc[0]))
    ending_capital = shares * float(prices.iloc[-1]) - sell_commission

    return BenchmarkResult(
        name=name,
        capital=capital,
        gross_return_pct=(gross_ending_capital - capital) / capital,
        net_return_pct=(ending_capital - capital) / capital,
        ending_capital=ending_capital,
        maximum_drawdown_pct=calculate_price_drawdown(prices),
        number_of_trades=2,
        total_commissions=buy_commission + sell_commission,
        category="benchmark",
    )


def build_equal_weight_benchmark(
    watchlist,
    histories: dict[str, pd.DataFrame],
    capital: float,
    config: AppConfig,
) -> BenchmarkResult | None:
    available_tickers = [item.ticker for item in watchlist if item.ticker in histories and not histories[item.ticker].empty]
    if not available_tickers:
        return None

    per_ticker_capital = capital / len(available_tickers)
    gross_end_values = []
    net_end_values = []
    equity_curve_parts = []

    for ticker in available_tickers:
        prices = histories[ticker]["Close"].dropna()
        if len(prices) < 2:
            continue
        buy_commission = config.transaction_costs.fixed_nok
        sell_commission = config.transaction_costs.fixed_nok
        shares = max(0, per_ticker_capital - buy_commission) / float(prices.iloc[0])
        gross_end_values.append(per_ticker_capital * (float(prices.iloc[-1]) / float(prices.iloc[0])))
        net_end_values.append(shares * float(prices.iloc[-1]) - sell_commission)
        equity_curve_parts.append((prices / float(prices.iloc[0])) * per_ticker_capital)

    if not gross_end_values:
        return None

    equity_curve = pd.concat(equity_curve_parts, axis=1).ffill().dropna().sum(axis=1)
    total_commissions = len(gross_end_values) * config.transaction_costs.fixed_nok * 2
    ending_capital = sum(net_end_values)
    gross_ending_capital = sum(gross_end_values)

    return BenchmarkResult(
        name="Equal-weight buy and hold watchlist",
        capital=capital,
        gross_return_pct=(gross_ending_capital - capital) / capital,
        net_return_pct=(ending_capital - capital) / capital,
        ending_capital=ending_capital,
        maximum_drawdown_pct=calculate_equity_drawdown(equity_curve),
        number_of_trades=len(gross_end_values) * 2,
        total_commissions=total_commissions,
        category="benchmark",
    )


def calculate_price_drawdown(prices: pd.Series) -> float:
    equity = prices / float(prices.iloc[0])
    return calculate_equity_drawdown(equity)


def calculate_equity_drawdown(equity_curve: pd.Series) -> float:
    running_peak = equity_curve.cummax()
    drawdowns = (equity_curve - running_peak) / running_peak
    return float(drawdowns.min())


def write_benchmark_report(results: list[BenchmarkResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Benchmark Comparison Report",
        "",
        "This is a historical research comparison only. It is not financial advice.",
        "Fixed Nordnet Mini commission: 29 NOK per buy and 29 NOK per final sell.",
        "",
        "| Strategy / Benchmark | Capital | Gross return | Net return after commission | Ending capital | Max drawdown | Number of trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for result in sorted(results, key=lambda item: (item.capital, item.category, item.name)):
        lines.append(
            f"| {result.name} | {result.capital:,.0f} NOK | {result.gross_return_pct:.2%} | "
            f"{result.net_return_pct:.2%} | {result.ending_capital:,.2f} NOK | "
            f"{result.maximum_drawdown_pct:.2%} | {result.number_of_trades} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        build_benchmark_interpretation(results),
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_benchmark_interpretation(results: list[BenchmarkResult]) -> str:
    if not results:
        return "No benchmark results were generated."

    bot_results = [result for result in results if result.category == "bot"]
    benchmark_results = [result for result in results if result.category == "benchmark"]
    single_stock = [result for result in benchmark_results if result.name.startswith("Buy and hold")]
    market_proxies = [
        result for result in benchmark_results
        if "proxy" in result.name or "Equal-weight" in result.name
    ]

    best_bot = max(bot_results, key=lambda item: item.net_return_pct) if bot_results else None
    best_buy_hold = max(single_stock, key=lambda item: item.net_return_pct) if single_stock else None
    best_market = max(market_proxies, key=lambda item: item.net_return_pct) if market_proxies else None
    best_passive = max(benchmark_results, key=lambda item: item.net_return_pct) if benchmark_results else None

    lines = []
    if best_bot and best_buy_hold:
        outcome = "beat" if best_bot.net_return_pct > best_buy_hold.net_return_pct else "did not beat"
        lines.append(
            f"The best bot mode {outcome} the best single-stock buy-and-hold benchmark: "
            f"{best_bot.name} ({best_bot.net_return_pct:.2%}) vs {best_buy_hold.name} ({best_buy_hold.net_return_pct:.2%})."
        )
    if best_bot and best_market:
        outcome = "beat" if best_bot.net_return_pct > best_market.net_return_pct else "did not beat"
        lines.append(
            f"The best bot mode {outcome} the broad market/proxy benchmark: "
            f"{best_bot.name} ({best_bot.net_return_pct:.2%}) vs {best_market.name} ({best_market.net_return_pct:.2%})."
        )
    if best_passive:
        lines.append(
            f"The best passive benchmark was {best_passive.name} at {best_passive.net_return_pct:.2%} net return."
        )
    if best_bot and best_passive:
        if best_bot.net_return_pct > best_passive.net_return_pct:
            lines.append("The bot added value versus passive investing in this historical window.")
        else:
            lines.append("The bot did not add value versus passive investing in this historical window.")

    return "\n\n".join(lines)
