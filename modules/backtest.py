from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from modules.config import AppConfig
from modules.strategy import StockAnalysis, analyze_price_history


PREVIOUS_75_NOK_RESULTS = {
    "robust_current": {
        "gross_return_pct": -0.0823,
        "net_return_pct": -0.1911,
        "total_commissions": 2175.0,
        "number_of_trades": 29,
        "buy_trades": 15,
        "sell_trades": 14,
        "maximum_drawdown_pct": -0.2014,
        "ending_capital": 16178.63,
        "cash_remaining": 8227.33,
    },
    "ultra_selective": {
        "gross_return_pct": -0.0611,
        "net_return_pct": -0.1023,
        "total_commissions": 825.0,
        "number_of_trades": 11,
        "buy_trades": 6,
        "sell_trades": 5,
        "maximum_drawdown_pct": -0.1999,
        "ending_capital": 17953.87,
        "cash_remaining": 2630.37,
    },
    "max_3_trades": {
        "gross_return_pct": -0.1517,
        "net_return_pct": -0.1742,
        "total_commissions": 450.0,
        "number_of_trades": 6,
        "buy_trades": 3,
        "sell_trades": 3,
        "maximum_drawdown_pct": -0.1755,
        "ending_capital": 16515.78,
        "cash_remaining": 16515.78,
    },
}


class WatchlistLike(Protocol):
    ticker: str
    name: str
    market: str


@dataclass
class Position:
    ticker: str
    name: str
    market: str
    shares: float
    entry_price: float
    stop_loss: float
    target_price: float
    entry_date: pd.Timestamp
    entry_day_index: int
    score: int
    confidence_score: int
    volatility: float


@dataclass(frozen=True)
class Trade:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    gain_pct: float
    pnl: float
    reason: str
    commission: float
    holding_days: int


@dataclass
class CommissionStats:
    total_commissions: float = 0.0
    buy_trades: int = 0
    sell_trades: int = 0


@dataclass(frozen=True)
class StrategyMode:
    name: str
    max_positions: int
    min_trade_size_nok: float
    cash_reserve_pct: float
    max_new_positions_per_rebalance: int
    rebalance_frequency: str
    min_holding_days: int
    min_score_for_buy: int
    min_score_for_reentry: int
    min_confidence_for_buy: int = 0
    max_volatility: float | None = None
    min_momentum_30d: float | None = None
    require_price_above_sma20: bool = False
    require_sma20_above_sma50: bool = False
    require_buy_signal: bool = True
    commission_guard_multiple: float = 4
    exit_score_threshold: int = 45
    max_completed_trades: int | None = None


@dataclass(frozen=True)
class BacktestResult:
    mode_name: str
    starting_capital: float
    ending_capital: float
    gross_return_pct: float
    net_return_pct: float
    number_of_trades: int
    buy_trades: int
    sell_trades: int
    total_commissions: float
    average_commission_per_trade: float
    average_holding_period_days: float
    win_rate_pct: float
    average_gain_pct: float
    average_loss_pct: float
    maximum_drawdown_pct: float
    best_trade: Trade | None
    worst_trade: Trade | None
    holdings: list[Position]
    cash_remaining: float
    average_portfolio_volatility: float
    portfolio_concentration: float
    cash_percentage: float


@dataclass(frozen=True)
class MomentumRank:
    analysis: StockAnalysis
    strength: float
    momentum_90d: float | None
    relative_strength: float | None


def run_backtest(watchlist: list[WatchlistLike], config: AppConfig) -> BacktestResult:
    histories = fetch_backtest_histories(watchlist, config.backtest.history_period)
    return run_backtest_with_histories(watchlist, histories, config, build_robust_current_mode(config))


def run_backtest_comparison(watchlist: list[WatchlistLike], config: AppConfig) -> list[BacktestResult]:
    histories = fetch_backtest_histories(watchlist, config.backtest.history_period)
    return [
        run_backtest_with_histories(watchlist, histories, config, mode)
        for mode in build_strategy_modes(config)
    ]


def run_capital_comparison(
    watchlist: list[WatchlistLike],
    config: AppConfig,
    capital_scenarios: list[float],
) -> list[BacktestResult]:
    histories = fetch_backtest_histories(watchlist, config.backtest.history_period)
    results = []
    for capital in capital_scenarios:
        for mode in build_strategy_modes(config):
            results.append(run_backtest_with_histories(watchlist, histories, config, mode, capital))
    return results


def run_momentum_portfolio_backtest(
    watchlist: list[WatchlistLike],
    histories: dict[str, pd.DataFrame],
    config: AppConfig,
    starting_capital: float,
    benchmark_tickers: tuple[str, ...] = ("QQQ", "SPY"),
    top_n: int = 3,
    rebalance_frequency: str = "monthly",
    stop_loss_pct: float | None = None,
    minimum_momentum_threshold: float = 0.0,
    exclude_tickers: set[str] | None = None,
    mode_name: str = "momentum_portfolio",
    analysis_cache: dict[tuple[str, pd.Timestamp], StockAnalysis] | None = None,
) -> BacktestResult:
    excluded = exclude_tickers or set()
    active_watchlist = [item for item in watchlist if item.ticker not in excluded]
    watchlist_tickers = {item.ticker for item in active_watchlist}
    trading_dates = get_trading_dates({ticker: history for ticker, history in histories.items() if ticker in watchlist_tickers})
    if not trading_dates:
        raise ValueError("No historical data available for momentum portfolio backtest")

    cash = starting_capital
    positions: dict[str, Position] = {}
    trades: list[Trade] = []
    commission_stats = CommissionStats()
    equity_curve = []
    rebalance_dates = set(get_rebalance_dates(trading_dates, rebalance_frequency))
    watchlist_by_ticker = {item.ticker: item for item in active_watchlist}
    active_stop_loss_pct = config.risk.stop_loss_pct if stop_loss_pct is None else stop_loss_pct

    for day_index, current_date in enumerate(trading_dates):
        latest_prices = latest_prices_on_or_before(histories, current_date)
        cash = process_momentum_price_exits(
            day_index,
            current_date,
            latest_prices,
            histories,
            watchlist_by_ticker,
            positions,
            trades,
            cash,
            config,
            commission_stats,
            analysis_cache,
        )

        if current_date in rebalance_dates:
            rankings = rank_momentum_universe(active_watchlist, histories, current_date, config, benchmark_tickers, analysis_cache)
            rankings = [
                ranking for ranking in rankings
                if ranking.analysis.momentum_30d >= minimum_momentum_threshold
            ]
            top_rankings = rankings[:top_n]
            top_tickers = {ranking.analysis.ticker for ranking in top_rankings}
            analyses_by_ticker = {ranking.analysis.ticker: ranking.analysis for ranking in rankings}
            cash = process_momentum_rebalance_exits(
                day_index,
                current_date,
                top_tickers,
                analyses_by_ticker,
                latest_prices,
                positions,
                trades,
                cash,
                config,
                commission_stats,
            )
            cash = process_momentum_rebalance_buys(
                day_index,
                current_date,
                top_rankings,
                latest_prices,
                positions,
                cash,
                starting_capital,
                config,
                commission_stats,
                top_n,
                active_stop_loss_pct,
            )

        equity_curve.append(cash + calculate_positions_value(positions, latest_prices))

    final_prices = latest_prices_on_or_before(histories, trading_dates[-1])
    ending_capital = cash + calculate_positions_value(positions, final_prices)
    return build_backtest_result(
        starting_capital=starting_capital,
        mode_name=mode_name,
        ending_capital=ending_capital,
        cash=cash,
        positions=list(positions.values()),
        trades=trades,
        commission_stats=commission_stats,
        equity_curve=equity_curve,
        final_prices=final_prices,
    )


def rank_momentum_universe(
    watchlist: list[WatchlistLike],
    histories: dict[str, pd.DataFrame],
    current_date: pd.Timestamp,
    config: AppConfig,
    benchmark_tickers: tuple[str, ...] = ("QQQ", "SPY"),
    analysis_cache: dict[tuple[str, pd.Timestamp], StockAnalysis] | None = None,
) -> list[MomentumRank]:
    benchmark_history = first_available_history(histories, benchmark_tickers, current_date)
    rankings = []
    for item in watchlist:
        history = histories.get(item.ticker)
        if history is None:
            continue
        available = history.loc[history.index <= current_date]
        if len(available) < 50:
            continue
        analysis = analyze_price_history_cached(item, available, current_date, config, analysis_cache)
        momentum_90d = calculate_period_momentum(available, 90)
        relative_strength = calculate_relative_strength(available, benchmark_history, 30)
        strength = calculate_momentum_strength(analysis, momentum_90d, relative_strength)
        rankings.append(MomentumRank(analysis, strength, momentum_90d, relative_strength))

    return sorted(
        rankings,
        key=lambda item: (
            item.strength,
            item.analysis.momentum_30d,
            item.momentum_90d if item.momentum_90d is not None else -999,
            item.analysis.score,
        ),
        reverse=True,
    )


def analyze_price_history_cached(
    item: WatchlistLike,
    available: pd.DataFrame,
    current_date: pd.Timestamp,
    config: AppConfig,
    analysis_cache: dict[tuple[str, pd.Timestamp], StockAnalysis] | None = None,
) -> StockAnalysis:
    key = (item.ticker, pd.Timestamp(current_date).normalize())
    if analysis_cache is not None and key in analysis_cache:
        return analysis_cache[key]
    analysis = analyze_price_history(item, available, config.risk, config.signals)
    if analysis_cache is not None:
        analysis_cache[key] = analysis
    return analysis


def calculate_momentum_strength(
    analysis: StockAnalysis,
    momentum_90d: float | None,
    relative_strength: float | None,
) -> float:
    strength = analysis.momentum_30d * 100
    if momentum_90d is not None:
        strength += momentum_90d * 60
    if analysis.close > analysis.sma50:
        strength += 10
    else:
        strength -= 10
    if analysis.sma20 > analysis.sma50:
        strength += 5
    if relative_strength is not None:
        strength += relative_strength * 50
    return strength


def calculate_period_momentum(history: pd.DataFrame, periods: int) -> float | None:
    prices = history["Close"].dropna()
    if len(prices) <= periods:
        return None
    start = float(prices.iloc[-periods - 1])
    if start <= 0:
        return None
    return (float(prices.iloc[-1]) - start) / start


def first_available_history(
    histories: dict[str, pd.DataFrame],
    tickers: tuple[str, ...],
    current_date: pd.Timestamp,
) -> pd.DataFrame | None:
    for ticker in tickers:
        history = histories.get(ticker)
        if history is None:
            continue
        available = history.loc[history.index <= current_date]
        if len(available) >= 31:
            return available
    return None


def calculate_relative_strength(
    stock_history: pd.DataFrame,
    benchmark_history: pd.DataFrame | None,
    periods: int,
) -> float | None:
    if benchmark_history is None:
        return None
    stock_momentum = calculate_period_momentum(stock_history, periods)
    benchmark_momentum = calculate_period_momentum(benchmark_history, periods)
    if stock_momentum is None or benchmark_momentum is None:
        return None
    return stock_momentum - benchmark_momentum


def process_momentum_price_exits(
    day_index: int,
    current_date: pd.Timestamp,
    prices: dict[str, float],
    histories: dict[str, pd.DataFrame],
    watchlist_by_ticker: dict[str, WatchlistLike],
    positions: dict[str, Position],
    trades: list[Trade],
    cash: float,
    config: AppConfig,
    commission_stats: CommissionStats,
    analysis_cache: dict[tuple[str, pd.Timestamp], StockAnalysis] | None = None,
) -> float:
    for ticker, position in list(positions.items()):
        price = prices.get(ticker)
        if price is None:
            continue
        if price <= position.stop_loss:
            cash = close_position_without_cooldown(
                day_index,
                current_date,
                price,
                "stop_loss",
                position,
                positions,
                trades,
                cash,
                config,
                commission_stats,
            )
            continue
        item = watchlist_by_ticker.get(ticker)
        history = histories.get(ticker)
        if item is None or history is None:
            continue
        available = history.loc[history.index <= current_date]
        if len(available) < 50:
            continue
        analysis = analyze_price_history_cached(item, available, current_date, config, analysis_cache)
        if is_severe_sell_signal(analysis):
            cash = close_position_without_cooldown(
                day_index,
                current_date,
                price,
                "severe_sell_signal",
                position,
                positions,
                trades,
                cash,
                config,
                commission_stats,
            )
    return cash


def process_momentum_rebalance_exits(
    day_index: int,
    current_date: pd.Timestamp,
    top_tickers: set[str],
    analyses_by_ticker: dict[str, StockAnalysis],
    prices: dict[str, float],
    positions: dict[str, Position],
    trades: list[Trade],
    cash: float,
    config: AppConfig,
    commission_stats: CommissionStats,
) -> float:
    for ticker, position in list(positions.items()):
        price = prices.get(ticker)
        if price is None:
            continue
        analysis = analyses_by_ticker.get(ticker)
        if ticker not in top_tickers:
            cash = close_position_without_cooldown(
                day_index,
                current_date,
                price,
                "left_top_3",
                position,
                positions,
                trades,
                cash,
                config,
                commission_stats,
            )
        elif analysis is not None and is_severe_sell_signal(analysis):
            cash = close_position_without_cooldown(
                day_index,
                current_date,
                price,
                "severe_sell_signal",
                position,
                positions,
                trades,
                cash,
                config,
                commission_stats,
            )
    return cash


def process_momentum_rebalance_buys(
    day_index: int,
    current_date: pd.Timestamp,
    top_rankings: list[MomentumRank],
    prices: dict[str, float],
    positions: dict[str, Position],
    cash: float,
    starting_capital: float,
    config: AppConfig,
    commission_stats: CommissionStats,
    top_n: int,
    stop_loss_pct: float,
) -> float:
    if not top_rankings:
        return cash

    latest_portfolio_value = cash + calculate_positions_value(positions, prices)
    target_position_value = latest_portfolio_value / top_n
    minimum_trade_size = min(config.trading.min_trade_size_nok, starting_capital / top_n)

    for ranking in top_rankings:
        analysis = ranking.analysis
        if analysis.ticker in positions or analysis.ticker not in prices:
            continue
        target_cash = min(target_position_value, cash - config.transaction_costs.fixed_nok)
        if target_cash < minimum_trade_size:
            continue
        fee = calculate_transaction_cost(target_cash, config)
        if target_cash + fee > cash:
            target_cash = cash - fee
        if target_cash <= 0:
            continue
        price = prices[analysis.ticker]
        shares = target_cash / price
        if shares <= 0:
            continue
        cash -= target_cash + fee
        commission_stats.total_commissions += fee
        commission_stats.buy_trades += 1
        positions[analysis.ticker] = Position(
            ticker=analysis.ticker,
            name=analysis.name,
            market=analysis.market,
            shares=shares,
            entry_price=price,
            stop_loss=price * (1 - stop_loss_pct),
            target_price=price * (1 + config.risk.take_profit_pct),
            entry_date=current_date,
            entry_day_index=day_index,
            score=analysis.score,
            confidence_score=analysis.confidence_score,
            volatility=analysis.volatility,
        )
    return cash


def is_severe_sell_signal(analysis: StockAnalysis) -> bool:
    return analysis.signal == "SELL" and analysis.close < analysis.sma50 and analysis.momentum_30d < -0.12


def close_position_without_cooldown(
    day_index: int,
    current_date: pd.Timestamp,
    price: float,
    reason: str,
    position: Position,
    positions: dict[str, Position],
    trades: list[Trade],
    cash: float,
    config: AppConfig,
    commission_stats: CommissionStats,
) -> float:
    return close_position(
        day_index,
        current_date,
        price,
        reason,
        position,
        positions,
        trades,
        cash,
        config,
        cooldown_until={},
        commission_stats=commission_stats,
    )


def run_backtest_with_histories(
    watchlist: list[WatchlistLike],
    histories: dict[str, pd.DataFrame],
    config: AppConfig,
    mode: StrategyMode,
    starting_capital: float | None = None,
) -> BacktestResult:
    trading_dates = get_trading_dates(histories)
    if not trading_dates:
        raise ValueError("No historical data available for backtest")

    capital = starting_capital if starting_capital is not None else config.portfolio.capital_nok
    cash = capital
    positions: dict[str, Position] = {}
    trades: list[Trade] = []
    commission_stats = CommissionStats()
    equity_curve = []
    cooldown_until: dict[str, int] = {}
    rebalance_dates = set(get_rebalance_dates(trading_dates, mode.rebalance_frequency))

    for day_index, current_date in enumerate(trading_dates):
        latest_prices = latest_prices_on_or_before(histories, current_date)
        update_trailing_stops(latest_prices, positions)
        cash = process_price_exits(
            day_index,
            current_date,
            latest_prices,
            positions,
            trades,
            cash,
            config,
            mode,
            cooldown_until,
            commission_stats,
        )

        if current_date in rebalance_dates:
            analyses = analyze_universe_for_date(watchlist, histories, current_date, config)
            cash = process_signal_exits(
                day_index,
                current_date,
                analyses,
                latest_prices,
                positions,
                trades,
                cash,
                config,
                mode,
                cooldown_until,
                commission_stats,
            )
            cash = process_rebalance_buys(
                day_index,
                current_date,
                analyses,
                latest_prices,
                positions,
                cash,
                config,
                mode,
                capital,
                cooldown_until,
                commission_stats,
            )

        equity_curve.append(cash + calculate_positions_value(positions, latest_prices))

    final_prices = latest_prices_on_or_before(histories, trading_dates[-1])
    ending_capital = cash + calculate_positions_value(positions, final_prices)
    return build_backtest_result(
        starting_capital=capital,
        mode_name=mode.name,
        ending_capital=ending_capital,
        cash=cash,
        positions=list(positions.values()),
        trades=trades,
        commission_stats=commission_stats,
        equity_curve=equity_curve,
        final_prices=final_prices,
    )


def build_strategy_modes(config: AppConfig) -> list[StrategyMode]:
    return [
        build_robust_current_mode(config),
        StrategyMode(
            name="ultra_selective",
            max_positions=1,
            min_trade_size_nok=15000,
            cash_reserve_pct=0.20,
            max_new_positions_per_rebalance=1,
            rebalance_frequency="monthly",
            min_holding_days=60,
            min_score_for_buy=88,
            min_score_for_reentry=88,
            min_confidence_for_buy=75,
            max_volatility=0.35,
            min_momentum_30d=0.08,
            require_price_above_sma20=True,
            require_sma20_above_sma50=True,
            require_buy_signal=True,
            commission_guard_multiple=6,
            exit_score_threshold=50,
        ),
        StrategyMode(
            name="max_3_trades",
            max_positions=1,
            min_trade_size_nok=15000,
            cash_reserve_pct=0.20,
            max_new_positions_per_rebalance=1,
            rebalance_frequency="monthly",
            min_holding_days=60,
            min_score_for_buy=85,
            min_score_for_reentry=85,
            min_confidence_for_buy=70,
            require_buy_signal=True,
            commission_guard_multiple=4,
            exit_score_threshold=50,
            max_completed_trades=3,
        ),
    ]


def build_robust_current_mode(config: AppConfig) -> StrategyMode:
    return StrategyMode(
        name="robust_current",
        max_positions=config.portfolio.max_positions,
        min_trade_size_nok=config.trading.min_trade_size_nok,
        cash_reserve_pct=config.portfolio.cash_reserve_pct,
        max_new_positions_per_rebalance=config.trading.max_new_positions_per_rebalance,
        rebalance_frequency=config.backtest.rebalance_frequency,
        min_holding_days=config.trading.min_holding_days,
        min_score_for_buy=config.trading.min_score_for_buy,
        min_score_for_reentry=config.trading.min_score_for_reentry,
        require_buy_signal=True,
        commission_guard_multiple=4,
        exit_score_threshold=45,
    )


def fetch_backtest_histories(watchlist: list[WatchlistLike], period: str) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    histories = {}
    for item in watchlist:
        history = yf.download(
            item.ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if history.empty:
            continue
        if isinstance(history.columns, pd.MultiIndex):
            history.columns = history.columns.get_level_values(0)
        histories[item.ticker] = history.dropna(subset=["Close"]).copy()
    return histories


def get_trading_dates(histories: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    dates = set()
    for history in histories.values():
        dates.update(pd.Timestamp(index_value).normalize() for index_value in history.index)
    return sorted(dates)


def get_weekly_rebalance_dates(trading_dates: list[pd.Timestamp]) -> list[pd.Timestamp]:
    return get_rebalance_dates(trading_dates, "weekly")


def get_rebalance_dates(trading_dates: list[pd.Timestamp], frequency: str) -> list[pd.Timestamp]:
    dates = pd.Series(trading_dates)
    if frequency == "quarterly":
        period = "Q"
    elif frequency == "monthly":
        period = "M"
    else:
        period = "W"
    return list(dates.groupby(dates.dt.to_period(period)).max())


def latest_prices_on_or_before(
    histories: dict[str, pd.DataFrame],
    current_date: pd.Timestamp,
) -> dict[str, float]:
    prices = {}
    for ticker, history in histories.items():
        available = history.loc[history.index <= current_date]
        if not available.empty:
            prices[ticker] = float(available.iloc[-1]["Close"])
    return prices


def analyze_universe_for_date(
    watchlist: list[WatchlistLike],
    histories: dict[str, pd.DataFrame],
    current_date: pd.Timestamp,
    config: AppConfig,
) -> list[StockAnalysis]:
    analyses = []
    for item in watchlist:
        history = histories.get(item.ticker)
        if history is None:
            continue
        available = history.loc[history.index <= current_date]
        if len(available) < 50:
            continue
        analyses.append(analyze_price_history(item, available, config.risk, config.signals))
    return analyses


def process_price_exits(
    day_index: int,
    current_date: pd.Timestamp,
    prices: dict[str, float],
    positions: dict[str, Position],
    trades: list[Trade],
    cash: float,
    config: AppConfig,
    mode: StrategyMode,
    cooldown_until: dict[str, int],
    commission_stats: CommissionStats,
) -> float:
    for ticker, position in list(positions.items()):
        price = prices.get(ticker)
        if price is None:
            continue
        if price <= position.stop_loss:
            cash = close_position(day_index, current_date, price, "stop_loss", position, positions, trades, cash, config, cooldown_until, commission_stats)
        elif price >= position.target_price:
            cash = close_position(day_index, current_date, price, "target_price", position, positions, trades, cash, config, cooldown_until, commission_stats)
    return cash


def process_signal_exits(
    day_index: int,
    current_date: pd.Timestamp,
    analyses: list[StockAnalysis],
    prices: dict[str, float],
    positions: dict[str, Position],
    trades: list[Trade],
    cash: float,
    config: AppConfig,
    mode: StrategyMode,
    cooldown_until: dict[str, int],
    commission_stats: CommissionStats,
) -> float:
    analysis_by_ticker = {analysis.ticker: analysis for analysis in analyses}
    for ticker, position in list(positions.items()):
        analysis = analysis_by_ticker.get(ticker)
        price = prices.get(ticker)
        if analysis is None or price is None:
            continue
        holding_days = day_index - position.entry_day_index
        if holding_days < mode.min_holding_days:
            continue
        if analysis.score < mode.exit_score_threshold:
            cash = close_position(
                day_index,
                current_date,
                price,
                f"score_below_{mode.exit_score_threshold}",
                position,
                positions,
                trades,
                cash,
                config,
                cooldown_until,
                commission_stats,
            )
        elif analysis.signal == "SELL":
            cash = close_position(day_index, current_date, price, "sell_signal", position, positions, trades, cash, config, cooldown_until, commission_stats)
    return cash


def process_rebalance_buys(
    day_index: int,
    current_date: pd.Timestamp,
    analyses: list[StockAnalysis],
    prices: dict[str, float],
    positions: dict[str, Position],
    cash: float,
    config: AppConfig,
    mode: StrategyMode,
    capital: float | None,
    cooldown_until: dict[str, int],
    commission_stats: CommissionStats,
) -> float:
    if mode.max_completed_trades is not None and commission_stats.sell_trades >= mode.max_completed_trades:
        return cash

    open_slots = mode.max_positions - len(positions)
    if open_slots <= 0:
        return cash

    candidates = [
        analysis
        for analysis in analyses
        if analysis.ticker not in positions
        and day_index >= cooldown_until.get(analysis.ticker, -1)
        and is_entry_candidate(analysis, cooldown_until, config, mode)
        and analysis.ticker in prices
    ]
    candidates.sort(key=lambda item: (item.score, item.confidence_score, -item.volatility), reverse=True)

    max_new_positions = min(open_slots, mode.max_new_positions_per_rebalance)
    for analysis in candidates[:max_new_positions]:
        portfolio_capital = capital if capital is not None else config.portfolio.capital_nok
        max_position_amount = portfolio_capital * (1 - mode.cash_reserve_pct)
        target_cash = min(max_position_amount, cash / max(open_slots, 1))
        if target_cash < mode.min_trade_size_nok:
            break
        fee = calculate_transaction_cost(target_cash, config)
        if target_cash + fee > cash:
            target_cash = cash - fee
        if target_cash < mode.min_trade_size_nok:
            break
        if not passes_commission_impact_guard(target_cash, config, mode.commission_guard_multiple):
            continue
        price = prices[analysis.ticker]
        shares = target_cash / price
        if shares <= 0:
            continue
        cash -= target_cash + fee
        commission_stats.total_commissions += fee
        commission_stats.buy_trades += 1
        positions[analysis.ticker] = Position(
            ticker=analysis.ticker,
            name=analysis.name,
            market=analysis.market,
            shares=shares,
            entry_price=price,
            stop_loss=price * (1 - config.risk.stop_loss_pct),
            target_price=price * (1 + config.risk.take_profit_pct),
            entry_date=current_date,
            entry_day_index=day_index,
            score=analysis.score,
            confidence_score=analysis.confidence_score,
            volatility=analysis.volatility,
        )
        open_slots -= 1
        if open_slots <= 0:
            break
    return cash


def close_position(
    day_index: int,
    current_date: pd.Timestamp,
    price: float,
    reason: str,
    position: Position,
    positions: dict[str, Position],
    trades: list[Trade],
    cash: float,
    config: AppConfig,
    cooldown_until: dict[str, int],
    commission_stats: CommissionStats,
) -> float:
    gross_value = position.shares * price
    fee = calculate_transaction_cost(gross_value, config)
    cash += gross_value - fee
    commission_stats.total_commissions += fee
    commission_stats.sell_trades += 1
    pnl = (price - position.entry_price) * position.shares - fee
    gain_pct = (price - position.entry_price) / position.entry_price
    trades.append(Trade(
        ticker=position.ticker,
        entry_date=position.entry_date.strftime("%Y-%m-%d"),
        exit_date=current_date.strftime("%Y-%m-%d"),
        entry_price=round(position.entry_price, 4),
        exit_price=round(price, 4),
        shares=position.shares,
        gain_pct=gain_pct,
        pnl=pnl,
        reason=reason,
        commission=fee,
        holding_days=day_index - position.entry_day_index,
    ))
    del positions[position.ticker]
    cooldown_until[position.ticker] = day_index + 10
    return cash


def is_entry_candidate(
    analysis: StockAnalysis,
    cooldown_until: dict[str, int],
    config: AppConfig,
    mode: StrategyMode,
) -> bool:
    if mode.require_buy_signal and analysis.signal != "BUY":
        return False
    if analysis.score < required_entry_score(analysis.ticker, cooldown_until, mode):
        return False
    if analysis.confidence_score < mode.min_confidence_for_buy:
        return False
    if mode.max_volatility is not None and analysis.volatility >= mode.max_volatility:
        return False
    if mode.min_momentum_30d is not None and analysis.momentum_30d <= mode.min_momentum_30d:
        return False
    if mode.require_price_above_sma20 and analysis.close <= analysis.sma20:
        return False
    if mode.require_sma20_above_sma50 and analysis.sma20 <= analysis.sma50:
        return False
    return True


def required_entry_score(ticker: str, cooldown_until: dict[str, int], mode: StrategyMode) -> int:
    if ticker in cooldown_until:
        return mode.min_score_for_reentry
    return mode.min_score_for_buy


def passes_commission_impact_guard(amount: float, config: AppConfig, multiple: float = 4) -> bool:
    buy_commission = calculate_transaction_cost(amount, config)
    target_value = amount * (1 + config.risk.take_profit_pct)
    sell_commission = calculate_transaction_cost(target_value, config)
    target_profit = amount * config.risk.take_profit_pct
    return target_profit >= multiple * (buy_commission + sell_commission)


def update_trailing_stops(prices: dict[str, float], positions: dict[str, Position]) -> None:
    for ticker, position in positions.items():
        price = prices.get(ticker)
        if price is None:
            continue
        profit_pct = (price - position.entry_price) / position.entry_price
        if profit_pct > 0.15:
            position.stop_loss = max(position.stop_loss, price * 0.92)
        elif profit_pct > 0.10:
            position.stop_loss = max(position.stop_loss, position.entry_price)


def calculate_transaction_cost(amount: float, config: AppConfig) -> float:
    return config.transaction_costs.fixed_nok


def calculate_positions_value(positions: dict[str, Position], prices: dict[str, float]) -> float:
    return sum(position.shares * prices.get(ticker, position.entry_price) for ticker, position in positions.items())


def build_backtest_result(
    starting_capital: float,
    mode_name: str,
    ending_capital: float,
    cash: float,
    positions: list[Position],
    trades: list[Trade],
    commission_stats: CommissionStats,
    equity_curve: list[float],
    final_prices: dict[str, float],
) -> BacktestResult:
    gains = [trade.gain_pct for trade in trades if trade.gain_pct > 0]
    losses = [trade.gain_pct for trade in trades if trade.gain_pct <= 0]
    holding_periods = [trade.holding_days for trade in trades]
    best_trade = max(trades, key=lambda trade: trade.gain_pct) if trades else None
    worst_trade = min(trades, key=lambda trade: trade.gain_pct) if trades else None

    portfolio_value = cash + calculate_positions_value({position.ticker: position for position in positions}, final_prices)
    total_trade_count = commission_stats.buy_trades + commission_stats.sell_trades
    gross_ending_capital = ending_capital + commission_stats.total_commissions

    return BacktestResult(
        mode_name=mode_name,
        starting_capital=starting_capital,
        ending_capital=ending_capital,
        gross_return_pct=(gross_ending_capital - starting_capital) / starting_capital,
        net_return_pct=(ending_capital - starting_capital) / starting_capital,
        number_of_trades=total_trade_count,
        buy_trades=commission_stats.buy_trades,
        sell_trades=commission_stats.sell_trades,
        total_commissions=commission_stats.total_commissions,
        average_commission_per_trade=(commission_stats.total_commissions / total_trade_count) if total_trade_count else 0,
        average_holding_period_days=(sum(holding_periods) / len(holding_periods)) if holding_periods else 0,
        win_rate_pct=(len(gains) / len(trades)) if trades else 0,
        average_gain_pct=(sum(gains) / len(gains)) if gains else 0,
        average_loss_pct=(sum(losses) / len(losses)) if losses else 0,
        maximum_drawdown_pct=calculate_max_drawdown(equity_curve),
        best_trade=best_trade,
        worst_trade=worst_trade,
        holdings=positions,
        cash_remaining=cash,
        average_portfolio_volatility=calculate_average_portfolio_volatility(positions, final_prices),
        portfolio_concentration=calculate_portfolio_concentration(positions, final_prices, portfolio_value),
        cash_percentage=(cash / portfolio_value) if portfolio_value else 0,
    )


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    peak = None
    max_drawdown = 0.0
    for equity in equity_curve:
        if peak is None or equity > peak:
            peak = equity
        if peak:
            max_drawdown = min(max_drawdown, (equity - peak) / peak)
    return max_drawdown


def calculate_average_portfolio_volatility(
    positions: list[Position],
    prices: dict[str, float],
) -> float:
    total_value = sum(position.shares * prices.get(position.ticker, position.entry_price) for position in positions)
    if total_value <= 0:
        return 0.0
    return sum(
        position.volatility * ((position.shares * prices.get(position.ticker, position.entry_price)) / total_value)
        for position in positions
    )


def calculate_portfolio_concentration(
    positions: list[Position],
    prices: dict[str, float],
    portfolio_value: float,
) -> float:
    if portfolio_value <= 0 or not positions:
        return 0.0
    largest_position = max(position.shares * prices.get(position.ticker, position.entry_price) for position in positions)
    return largest_position / portfolio_value


def write_backtest_report(result: BacktestResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Backtest Report",
        "",
        "This is a historical simulation for research only. It is not financial advice.",
        "",
        f"- Starting capital: {result.starting_capital:,.2f} NOK",
        f"- Ending capital: {result.ending_capital:,.2f} NOK",
        f"- Gross return before commission: {result.gross_return_pct:.2%}",
        f"- Net return after commission: {result.net_return_pct:.2%}",
        f"- Number of trades: {result.number_of_trades}",
        f"- Number of buy trades: {result.buy_trades}",
        f"- Number of sell trades: {result.sell_trades}",
        f"- Total commissions paid: {result.total_commissions:,.2f} NOK",
        f"- Average commission per trade: {result.average_commission_per_trade:,.2f} NOK",
        f"- Average holding period: {result.average_holding_period_days:.1f} trading days",
        f"- Win rate: {result.win_rate_pct:.2%}",
        f"- Average gain: {result.average_gain_pct:.2%}",
        f"- Average loss: {result.average_loss_pct:.2%}",
        f"- Maximum drawdown: {result.maximum_drawdown_pct:.2%}",
        f"- Average portfolio volatility: {result.average_portfolio_volatility:.2%}",
        f"- Portfolio concentration: {result.portfolio_concentration:.2%}",
        f"- Cash percentage: {result.cash_percentage:.2%}",
        f"- Cash remaining: {result.cash_remaining:,.2f} NOK",
        "",
        "## Best Trade",
        "",
        format_trade(result.best_trade),
        "",
        "## Worst Trade",
        "",
        format_trade(result.worst_trade),
        "",
        "## Current Simulated Holdings",
        "",
    ]

    if result.holdings:
        lines.extend([
            "| Ticker | Name | Market | Shares | Entry | Stop | Target | Score | Confidence | Volatility |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for holding in result.holdings:
            lines.append(
                f"| {holding.ticker} | {holding.name} | {holding.market} | {holding.shares:.4f} | "
                f"{holding.entry_price:,.2f} | {holding.stop_loss:,.2f} | {holding.target_price:,.2f} | "
                f"{holding.score} | {holding.confidence_score} | {holding.volatility:.2%} |"
            )
    else:
        lines.append("No open simulated holdings.")

    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_backtest_comparison_report(results: list[BacktestResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Backtest Strategy Comparison",
        "",
        "This is a historical simulation for research only. It is not financial advice.",
        "News and AI analysis do not affect these trading signals.",
        "",
        "## Comparison",
        "",
        "| Mode | Gross return before commission | Net return after commission | Total commissions paid | Number of trades | Buy trades | Sell trades | Average holding period | Maximum drawdown | Ending capital | Cash remaining |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for result in results:
        lines.append(
            f"| {result.mode_name} | {result.gross_return_pct:.2%} | {result.net_return_pct:.2%} | "
            f"{result.total_commissions:,.2f} NOK | {result.number_of_trades} | "
            f"{result.buy_trades} | {result.sell_trades} | "
            f"{result.average_holding_period_days:.1f} days | {result.maximum_drawdown_pct:.2%} | "
            f"{result.ending_capital:,.2f} NOK | {result.cash_remaining:,.2f} NOK |"
        )

    lines.extend([
        "",
        "## Commission Correction Impact",
        "",
        "| Mode | 75 NOK net return | 29 NOK net return | Net return change | 75 NOK commissions | 29 NOK commissions | Commission savings | Ending capital change |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])

    for result in results:
        previous = PREVIOUS_75_NOK_RESULTS.get(result.mode_name)
        if previous is None:
            continue
        lines.append(
            f"| {result.mode_name} | {previous['net_return_pct']:.2%} | {result.net_return_pct:.2%} | "
            f"{result.net_return_pct - previous['net_return_pct']:.2%} | "
            f"{previous['total_commissions']:,.2f} NOK | {result.total_commissions:,.2f} NOK | "
            f"{previous['total_commissions'] - result.total_commissions:,.2f} NOK | "
            f"{result.ending_capital - previous['ending_capital']:,.2f} NOK |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        build_interpretation(results),
        "",
        "## Current Simulated Holdings",
        "",
    ])

    for result in results:
        lines.extend([
            f"### {result.mode_name}",
            "",
        ])
        if result.holdings:
            lines.extend([
                "| Ticker | Name | Market | Shares | Entry | Stop | Target | Score | Confidence | Volatility |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ])
            for holding in result.holdings:
                lines.append(
                    f"| {holding.ticker} | {holding.name} | {holding.market} | {holding.shares:.4f} | "
                    f"{holding.entry_price:,.2f} | {holding.stop_loss:,.2f} | {holding.target_price:,.2f} | "
                    f"{holding.score} | {holding.confidence_score} | {holding.volatility:.2%} |"
                )
        else:
            lines.append("No open simulated holdings.")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_capital_comparison_report(results: list[BacktestResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Capital Comparison Report",
        "",
        "This is a historical simulation for research only. It is not financial advice.",
        "Fixed Nordnet Mini commission: 29 NOK per trade.",
        "",
        "| Capital | Mode | Gross return | Net return | Ending capital | Total commissions | Commissions as % of capital | Number of trades | Max drawdown | Average holding period |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for result in sorted(results, key=lambda item: (item.starting_capital, item.mode_name)):
        commission_pct = result.total_commissions / result.starting_capital if result.starting_capital else 0
        lines.append(
            f"| {result.starting_capital:,.0f} NOK | {result.mode_name} | "
            f"{result.gross_return_pct:.2%} | {result.net_return_pct:.2%} | "
            f"{result.ending_capital:,.2f} NOK | {result.total_commissions:,.2f} NOK | "
            f"{commission_pct:.2%} | {result.number_of_trades} | "
            f"{result.maximum_drawdown_pct:.2%} | {result.average_holding_period_days:.1f} days |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        build_capital_interpretation(results),
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_capital_interpretation(results: list[BacktestResult]) -> str:
    by_capital: dict[float, list[BacktestResult]] = {}
    for result in results:
        by_capital.setdefault(result.starting_capital, []).append(result)

    lines = []
    for capital in sorted(by_capital):
        best = max(by_capital[capital], key=lambda item: item.net_return_pct)
        lines.append(
            f"Best mode for {capital:,.0f} NOK: {best.mode_name} ({best.net_return_pct:.2%} net return)."
        )

    best_20 = best_result_for_capital(by_capital, 20000)
    best_30 = best_result_for_capital(by_capital, 30000)
    if best_20 and best_30:
        improvement = best_30.net_return_pct - best_20.net_return_pct
        viable = best_30.net_return_pct > 0
        if viable:
            lines.append(
                f"Increasing to 30,000 NOK made the best tested mode positive after commission, improving net return by {improvement:.2%}."
            )
        else:
            lines.append(
                f"Increasing to 30,000 NOK improved the best-mode net return by {improvement:.2%}, but it did not make the strategy viable because the best 30,000 NOK result remains negative."
            )

    if results:
        best_overall = max(results, key=lambda item: item.net_return_pct)
        commission_drag = best_overall.gross_return_pct - best_overall.net_return_pct
        if best_overall.gross_return_pct < 0:
            lines.append(
                "The main issue is strategy performance: the best gross return before commission is still negative, so lower commission alone cannot fix the tested rules."
            )
        else:
            lines.append(
                f"Commission cost is meaningful but secondary here; the best-mode commission drag is {commission_drag:.2%}."
            )

    return "\n\n".join(lines)


def best_result_for_capital(
    by_capital: dict[float, list[BacktestResult]],
    capital: float,
) -> BacktestResult | None:
    results = by_capital.get(capital)
    if not results:
        return None
    return max(results, key=lambda item: item.net_return_pct)


def build_interpretation(results: list[BacktestResult]) -> str:
    if not results:
        return "No backtest results were generated."

    best_net = max(results, key=lambda result: result.net_return_pct)
    lowest_drawdown = max(results, key=lambda result: result.maximum_drawdown_pct)
    all_negative = all(result.net_return_pct < 0 for result in results)
    suitability = (
        "All tested modes were negative after the corrected 29 NOK commission, so the current strategy still appears unsuitable for a 20,000 NOK portfolio."
        if all_negative
        else "At least one mode was positive after the corrected 29 NOK commission, but commission drag remains important for a 20,000 NOK portfolio."
    )

    return (
        f"Best net return after commission: {best_net.mode_name} ({best_net.net_return_pct:.2%}). "
        f"Lowest drawdown: {lowest_drawdown.mode_name} ({lowest_drawdown.maximum_drawdown_pct:.2%}). "
        f"{suitability}"
    )


def format_trade(trade: Trade | None) -> str:
    if trade is None:
        return "No closed trades."
    return (
        f"{trade.ticker}: {trade.gain_pct:.2%} from {trade.entry_date} to {trade.exit_date} "
        f"({trade.reason}, {trade.holding_days} trading days)"
    )
