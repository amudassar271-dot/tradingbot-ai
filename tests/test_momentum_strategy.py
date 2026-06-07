from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from modules.backtest import (
    MomentumRank,
    calculate_momentum_strength,
    calculate_period_momentum,
    rank_momentum_universe,
    run_momentum_portfolio_backtest,
)
from modules.momentum_report import (
    MomentumReportRow,
    build_momentum_interpretation,
    write_momentum_strategy_report,
)


def make_config():
    return SimpleNamespace(
        risk=SimpleNamespace(stop_loss_pct=0.08, take_profit_pct=0.16, minimum_buy_score=75),
        signals=SimpleNamespace(sell_momentum_threshold=-0.08),
        trading=SimpleNamespace(min_trade_size_nok=0),
        transaction_costs=SimpleNamespace(fixed_nok=29),
    )


def make_item(ticker):
    return SimpleNamespace(ticker=ticker, name=ticker, market="US")


def make_history(prices):
    dates = pd.date_range("2025-01-01", periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_calculate_period_momentum_requires_enough_data():
    assert calculate_period_momentum(make_history([100] * 30), 30) is None
    assert calculate_period_momentum(make_history([100] * 31), 30) == 0


def test_momentum_strength_rewards_trend_and_relative_strength():
    analysis = SimpleNamespace(
        momentum_30d=0.10,
        close=120,
        sma20=115,
        sma50=100,
    )

    strength = calculate_momentum_strength(analysis, momentum_90d=0.25, relative_strength=0.05)

    assert strength == 42.5


def test_rank_momentum_universe_sorts_strongest_first():
    watchlist = [make_item("AAA"), make_item("BBB")]
    histories = {
        "AAA": make_history([100] * 70 + list(range(100, 130))),
        "BBB": make_history([100] * 100),
        "QQQ": make_history([100] * 100),
    }

    rankings = rank_momentum_universe(watchlist, histories, histories["AAA"].index[-1], make_config())

    assert [ranking.analysis.ticker for ranking in rankings] == ["AAA", "BBB"]


def test_momentum_backtest_uses_top_three_and_fixed_commission():
    watchlist = [make_item("AAA"), make_item("BBB"), make_item("CCC"), make_item("DDD")]
    histories = {
        "AAA": make_history([100] * 70 + list(range(100, 130))),
        "BBB": make_history([100] * 70 + list(range(100, 125)) + [124] * 5),
        "CCC": make_history([100] * 70 + list(range(100, 120)) + [119] * 10),
        "DDD": make_history([100] * 100),
        "QQQ": make_history([100] * 100),
    }

    result = run_momentum_portfolio_backtest(watchlist, histories, make_config(), 20000)

    assert result.mode_name == "momentum_portfolio"
    assert result.buy_trades == 3
    assert result.total_commissions == 87
    assert len(result.holdings) == 3


def test_write_momentum_strategy_report(tmp_path: Path):
    rows = [
        MomentumReportRow("momentum_portfolio", 20000, 0.12, 0.11, 22200, 174, 6, -0.08, "momentum", "AAA"),
        MomentumReportRow("robust_current", 20000, 0.02, 0.01, 20200, 58, 2, -0.05, "existing_bot", "Cash only"),
        MomentumReportRow("Equal-weight buy and hold watchlist", 20000, 0.10, 0.09, 21800, 58, 2, -0.12, "benchmark"),
        MomentumReportRow("Buy and hold NVDA", 20000, 0.20, 0.19, 23800, 58, 2, -0.20, "benchmark"),
        MomentumReportRow("Buy and hold QQQ", 20000, 0.08, 0.07, 21400, 58, 2, -0.10, "benchmark"),
        MomentumReportRow("Buy and hold SPY", 20000, 0.06, 0.05, 21000, 58, 2, -0.09, "benchmark"),
    ]
    output_path = tmp_path / "momentum_strategy_report.md"

    write_momentum_strategy_report(rows, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Momentum Portfolio Strategy Report" in content
    assert "momentum_portfolio" in content
    assert "Current Simulated Holdings" in content


def test_momentum_interpretation_compares_required_benchmarks():
    rows = [
        MomentumReportRow("momentum_portfolio", 20000, 0.12, 0.11, 22200, 174, 6, -0.08, "momentum"),
        MomentumReportRow("robust_current", 20000, 0.02, 0.01, 20200, 58, 2, -0.05, "existing_bot"),
        MomentumReportRow("Equal-weight buy and hold watchlist", 20000, 0.10, 0.09, 21800, 58, 2, -0.12, "benchmark"),
        MomentumReportRow("Buy and hold NVDA", 20000, 0.20, 0.19, 23800, 58, 2, -0.20, "benchmark"),
        MomentumReportRow("Buy and hold QQQ", 20000, 0.08, 0.07, 21400, 58, 2, -0.10, "benchmark"),
        MomentumReportRow("Buy and hold SPY", 20000, 0.06, 0.05, 21000, 58, 2, -0.09, "benchmark"),
    ]

    interpretation = build_momentum_interpretation(rows)

    assert "best existing bot mode" in interpretation
    assert "equal-weight watchlist" in interpretation
    assert "SPY/QQQ" in interpretation
    assert "NVDA" in interpretation
