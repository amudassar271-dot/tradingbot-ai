from pathlib import Path

import pandas as pd

from modules.config import load_config
from modules.market_data import WatchlistItem
from modules.strategy_report import build_primary_strategy_report, write_strategy_report


def make_history(prices):
    dates = pd.date_range("2025-01-01", periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_load_config_reads_primary_strategy(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
portfolio:
  capital_nok: 20000
  max_positions: 2
  position_sizing: score_weighted
  max_position_pct: 0.50
  cash_reserve_pct: 0.05
risk:
  stop_loss_pct: 0.08
  take_profit_pct: 0.16
  minimum_buy_score: 75
transaction_cost:
  fixed_nok: 29
primary_strategy:
  name: momentum_portfolio
  top_n: 2
  rebalance_frequency: monthly
  stop_loss_pct: 15
  momentum_threshold_pct: 10
  capital_nok: 30000
trading:
  min_trade_size_nok: 7500
backtest:
  history_period: 2y
  rebalance_frequency: monthly
  output_path: reports/backtest_report.md
news:
  enabled: true
signals:
  sell_momentum_threshold: -0.08
report:
  schedule: daily
  output_path: reports/daily_report.md
market_data:
  watchlist_path: data/watchlist.csv
  history_months: 6
""",
        encoding="utf-8",
    )

    config = load_config(config_path, tmp_path)

    assert config.primary_strategy.name == "momentum_portfolio"
    assert config.primary_strategy.top_n == 2
    assert config.primary_strategy.stop_loss_pct == 0.15
    assert config.primary_strategy.momentum_threshold_pct == 0.10
    assert config.primary_strategy.capital_nok == 30000


def test_build_primary_strategy_report_selects_top_two(monkeypatch):
    watchlist = [
        WatchlistItem("AAA", "AAA Inc", "US"),
        WatchlistItem("BBB", "BBB Inc", "US"),
        WatchlistItem("CCC", "CCC Inc", "US"),
    ]
    histories = {
        "AAA": make_history([100] * 70 + list(range(100, 140))),
        "BBB": make_history([100] * 70 + list(range(100, 130)) + [129] * 10),
        "CCC": make_history([100] * 110),
        "QQQ": make_history([100] * 110),
        "SPY": make_history([100] * 110),
    }

    def fake_fetch_backtest_histories(items, period):
        return histories

    monkeypatch.setattr("modules.strategy_report.fetch_backtest_histories", fake_fetch_backtest_histories)
    config = load_config(Path("config.yaml"), Path.cwd())

    report = build_primary_strategy_report(watchlist, config)

    assert report.strategy_name == "momentum_portfolio"
    assert [candidate.ticker for candidate in report.candidates] == ["AAA", "BBB"]
    assert report.candidates[0].stop_loss < report.candidates[0].entry_price
    assert report.cash_reserve_nok >= 0


def test_write_strategy_report_contains_required_sections(tmp_path: Path, monkeypatch):
    watchlist = [
        WatchlistItem("AAA", "AAA Inc", "US"),
        WatchlistItem("BBB", "BBB Inc", "US"),
    ]
    histories = {
        "AAA": make_history([100] * 70 + list(range(100, 140))),
        "BBB": make_history([100] * 70 + list(range(100, 130)) + [129] * 10),
        "QQQ": make_history([100] * 110),
        "SPY": make_history([100] * 110),
    }

    monkeypatch.setattr("modules.strategy_report.fetch_backtest_histories", lambda items, period: histories)
    config = load_config(Path("config.yaml"), Path.cwd())
    report = build_primary_strategy_report(watchlist, config)
    output_path = tmp_path / "strategy_report.md"

    write_strategy_report(report, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Current Top Momentum Candidates" in content
    assert "Human decision required" in content
    assert "Why these stocks?" in content
    assert "This is not automatic trading" in content
    assert "Nordnet" in content
    assert "News and AI are context only" in content
