from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from modules.backtest import (
    BacktestResult,
    CommissionStats,
    Position,
    StrategyMode,
    Trade,
    calculate_average_portfolio_volatility,
    calculate_max_drawdown,
    calculate_portfolio_concentration,
    calculate_transaction_cost,
    close_position,
    passes_commission_impact_guard,
    process_rebalance_buys,
    update_trailing_stops,
    write_backtest_report,
    write_capital_comparison_report,
)


def make_mode(**overrides):
    values = {
        "name": "test_mode",
        "max_positions": 1,
        "min_trade_size_nok": 0,
        "cash_reserve_pct": 0.75,
        "max_new_positions_per_rebalance": 1,
        "rebalance_frequency": "monthly",
        "min_holding_days": 30,
        "min_score_for_buy": 75,
        "min_score_for_reentry": 88,
        "commission_guard_multiple": 4,
    }
    values.update(overrides)
    return StrategyMode(**values)


def test_transaction_cost_uses_minimum_fee():
    config = SimpleNamespace(transaction_costs=SimpleNamespace(fixed_nok=29))

    assert calculate_transaction_cost(4000, config) == 29


def test_transaction_cost_uses_rate_when_larger_than_minimum():
    config = SimpleNamespace(transaction_costs=SimpleNamespace(fixed_nok=29))

    assert calculate_transaction_cost(100000, config) == 29


def test_commission_is_deducted_on_buy_and_sell():
    config = SimpleNamespace(
        portfolio=SimpleNamespace(max_positions=1, capital_nok=20000, max_position_pct=0.25),
        risk=SimpleNamespace(stop_loss_pct=0.08, take_profit_pct=0.16, minimum_buy_score=75),
        trading=SimpleNamespace(
            min_trade_size_nok=0,
            max_new_positions_per_rebalance=1,
            min_score_for_buy=75,
            min_score_for_reentry=88,
        ),
        transaction_costs=SimpleNamespace(fixed_nok=29),
    )
    analysis = SimpleNamespace(
        ticker="AAA",
        name="AAA Inc",
        market="US",
        signal="BUY",
        score=80,
        confidence_score=75,
        volatility=0.20,
    )
    positions = {}
    trades = []
    commission_stats = CommissionStats()

    cash_after_buy = process_rebalance_buys(
        day_index=0,
        current_date=pd.Timestamp("2026-01-01"),
        analyses=[analysis],
        prices={"AAA": 100},
        positions=positions,
        cash=10000,
        config=config,
        mode=make_mode(),
        capital=20000,
        cooldown_until={},
        commission_stats=commission_stats,
    )

    assert cash_after_buy == 4971
    assert commission_stats.total_commissions == 29
    assert commission_stats.buy_trades == 1

    cash_after_sell = close_position(
        day_index=1,
        current_date=pd.Timestamp("2026-01-02"),
        price=100,
        reason="test_exit",
        position=positions["AAA"],
        positions=positions,
        trades=trades,
        cash=cash_after_buy,
        config=config,
        cooldown_until={},
        commission_stats=commission_stats,
    )

    assert cash_after_sell == 9942
    assert commission_stats.total_commissions == 58
    assert commission_stats.sell_trades == 1


def test_calculate_max_drawdown():
    drawdown = calculate_max_drawdown([100, 120, 90, 110])

    assert round(drawdown, 4) == -0.25


def test_minimum_trade_size_blocks_small_positions():
    config = SimpleNamespace(
        portfolio=SimpleNamespace(max_positions=1, capital_nok=20000, max_position_pct=0.25),
        risk=SimpleNamespace(stop_loss_pct=0.08, take_profit_pct=0.16, minimum_buy_score=75),
        trading=SimpleNamespace(
            min_trade_size_nok=7500,
            max_new_positions_per_rebalance=1,
            min_score_for_buy=82,
            min_score_for_reentry=88,
        ),
        transaction_costs=SimpleNamespace(fixed_nok=29),
    )
    analysis = SimpleNamespace(
        ticker="AAA",
        name="AAA Inc",
        market="US",
        signal="BUY",
        score=90,
        confidence_score=80,
        volatility=0.20,
    )

    cash = process_rebalance_buys(
        day_index=0,
        current_date=pd.Timestamp("2026-01-01"),
        analyses=[analysis],
        prices={"AAA": 100},
        positions={},
        cash=10000,
        config=config,
        mode=make_mode(min_trade_size_nok=7500),
        capital=20000,
        cooldown_until={},
        commission_stats=CommissionStats(),
    )

    assert cash == 10000


def test_commission_impact_guard_requires_target_profit_multiple():
    config = SimpleNamespace(
        risk=SimpleNamespace(take_profit_pct=0.16),
        transaction_costs=SimpleNamespace(fixed_nok=29),
    )

    assert not passes_commission_impact_guard(1000, config)
    assert passes_commission_impact_guard(7500, config)


def test_update_trailing_stop_moves_to_breakeven():
    position = Position("AAA", "AAA Inc", "US", 10, 100, 92, 116, None, 0, 80, 75, 0.20)

    update_trailing_stops({"AAA": 111}, {"AAA": position})

    assert position.stop_loss == 100


def test_update_trailing_stop_trails_after_15_percent_profit():
    position = Position("AAA", "AAA Inc", "US", 10, 100, 100, 120, None, 0, 80, 75, 0.20)

    update_trailing_stops({"AAA": 116}, {"AAA": position})

    assert round(position.stop_loss, 2) == 106.72


def test_portfolio_risk_metrics():
    positions = [
        Position("AAA", "AAA Inc", "US", 10, 100, 92, 116, None, 0, 80, 75, 0.20),
        Position("BBB", "BBB Inc", "US", 10, 50, 46, 58, None, 0, 80, 75, 0.40),
    ]
    prices = {"AAA": 100, "BBB": 50}

    assert round(calculate_average_portfolio_volatility(positions, prices), 4) == 0.2667
    assert round(calculate_portfolio_concentration(positions, prices, 2000), 4) == 0.5


def test_write_backtest_report(tmp_path: Path):
    result = BacktestResult(
        mode_name="test_mode",
        starting_capital=20000,
        ending_capital=21000,
        gross_return_pct=0.0575,
        net_return_pct=0.05,
        number_of_trades=2,
        buy_trades=1,
        sell_trades=1,
        total_commissions=150,
        average_commission_per_trade=75,
        average_holding_period_days=14,
        win_rate_pct=1,
        average_gain_pct=0.05,
        average_loss_pct=0,
        maximum_drawdown_pct=-0.02,
        best_trade=Trade("AAA", "2026-01-01", "2026-01-15", 100, 105, 10, 0.05, 500, "target_price", 75, 14),
        worst_trade=Trade("AAA", "2026-01-01", "2026-01-15", 100, 105, 10, 0.05, 500, "target_price", 75, 14),
        holdings=[],
        cash_remaining=21000,
        average_portfolio_volatility=0.18,
        portfolio_concentration=0.25,
        cash_percentage=0.15,
    )
    output_path = tmp_path / "backtest_report.md"

    write_backtest_report(result, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Starting capital" in content
    assert "Ending capital" in content
    assert "Gross return before commission" in content
    assert "Net return after commission" in content
    assert "Total commissions paid" in content
    assert "Average commission per trade" in content
    assert "Average holding period" in content
    assert "Number of buy trades" in content
    assert "Number of sell trades" in content
    assert "Average portfolio volatility" in content
    assert "Portfolio concentration" in content
    assert "Cash percentage" in content
    assert "Current Simulated Holdings" in content


def test_write_capital_comparison_report(tmp_path: Path):
    output_path = tmp_path / "capital_comparison_report.md"
    results = [
        BacktestResult(
            mode_name="robust_current",
            starting_capital=20000,
            ending_capital=19000,
            gross_return_pct=-0.04,
            net_return_pct=-0.05,
            number_of_trades=2,
            buy_trades=1,
            sell_trades=1,
            total_commissions=58,
            average_commission_per_trade=29,
            average_holding_period_days=30,
            win_rate_pct=0,
            average_gain_pct=0,
            average_loss_pct=-0.05,
            maximum_drawdown_pct=-0.10,
            best_trade=None,
            worst_trade=None,
            holdings=[],
            cash_remaining=19000,
            average_portfolio_volatility=0,
            portfolio_concentration=0,
            cash_percentage=1,
        ),
        BacktestResult(
            mode_name="ultra_selective",
            starting_capital=30000,
            ending_capital=30300,
            gross_return_pct=0.012,
            net_return_pct=0.01,
            number_of_trades=2,
            buy_trades=1,
            sell_trades=1,
            total_commissions=58,
            average_commission_per_trade=29,
            average_holding_period_days=40,
            win_rate_pct=1,
            average_gain_pct=0.01,
            average_loss_pct=0,
            maximum_drawdown_pct=-0.05,
            best_trade=None,
            worst_trade=None,
            holdings=[],
            cash_remaining=30300,
            average_portfolio_volatility=0,
            portfolio_concentration=0,
            cash_percentage=1,
        ),
    ]

    write_capital_comparison_report(results, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Capital Comparison Report" in content
    assert "Commissions as % of capital" in content
    assert "Best mode for 20,000 NOK" in content
    assert "Best mode for 30,000 NOK" in content
