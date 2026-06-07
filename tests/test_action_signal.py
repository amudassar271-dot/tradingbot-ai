from pathlib import Path

from modules.action_signal import (
    CurrentHolding,
    append_positions_history,
    build_action_signals,
    ensure_portfolio_state_files,
    load_current_holdings,
    write_action_signal_report,
    write_portfolio_journal,
)
from modules.strategy_report import PrimaryStrategyReport, StrategyCandidate


def make_candidate(ticker="AAA", name="AAA Inc", price=100):
    return StrategyCandidate(
        ticker=ticker,
        name=name,
        market="US",
        rank=1,
        allocation_nok=10000,
        entry_price=price,
        stop_loss=85,
        momentum_score=80,
        momentum_30d=0.15,
        momentum_90d=0.30,
        relative_strength=0.05,
        reason="strong momentum",
    )


def make_report(candidates=None):
    return PrimaryStrategyReport(
        strategy_name="momentum_portfolio",
        capital_nok=30000,
        top_n=2,
        rebalance_frequency="monthly",
        stop_loss_pct=0.15,
        momentum_threshold_pct=0.10,
        commission_nok=29,
        candidates=candidates if candidates is not None else [make_candidate()],
        cash_reserve_nok=0,
        replacement_note="",
    )


def test_buy_signal_when_no_holdings_exist():
    signals = build_action_signals(make_report(), {})

    assert any(signal.action == "BUY NOW" and signal.ticker == "AAA" for signal in signals)


def test_sell_signal_when_current_holding_is_not_target():
    holdings = {"BBB": CurrentHolding("BBB", shares=5, avg_price=90)}

    signals = build_action_signals(make_report(), holdings, {"BBB": 95})

    sell_signal = next(signal for signal in signals if signal.action == "SELL NOW")
    assert sell_signal.ticker == "BBB"
    assert sell_signal.current_price == 95
    assert sell_signal.estimated_value == 475


def test_hold_signal_when_current_holding_remains_target():
    holdings = {"AAA": CurrentHolding("AAA", shares=4, avg_price=80)}

    signals = build_action_signals(make_report(), holdings)

    assert any(signal.action == "HOLD" and signal.ticker == "AAA" for signal in signals)


def test_no_action_when_portfolio_already_matches_target():
    holdings = {"AAA": CurrentHolding("AAA", shares=4, avg_price=80)}

    signals = build_action_signals(make_report(), holdings)

    assert any(signal.action == "NO ACTION TODAY" for signal in signals)
    assert not any(signal.action in {"BUY NOW", "SELL NOW"} for signal in signals)


def test_load_current_holdings(tmp_path: Path):
    holdings_path = tmp_path / "current_holdings.csv"
    holdings_path.write_text("ticker,shares,avg_price\nAAA,4,80\n", encoding="utf-8")

    holdings = load_current_holdings(holdings_path)

    assert holdings["AAA"].shares == 4
    assert holdings["AAA"].avg_price == 80


def test_missing_holdings_file_is_created(tmp_path: Path):
    holdings_path = tmp_path / "current_holdings.csv"

    holdings = load_current_holdings(holdings_path)

    assert holdings == {}
    assert holdings_path.read_text(encoding="utf-8") == "ticker,shares,avg_price\n"


def test_empty_holdings_file_means_no_holdings(tmp_path: Path):
    holdings_path = tmp_path / "current_holdings.csv"
    holdings_path.write_text("ticker,shares,avg_price\n", encoding="utf-8")

    holdings = load_current_holdings(holdings_path)
    signals = build_action_signals(make_report(), holdings)

    assert holdings == {}
    assert any(signal.action == "BUY NOW" for signal in signals)


def test_startup_checks_create_state_files(tmp_path: Path):
    holdings_path = tmp_path / "data" / "current_holdings.csv"
    history_path = tmp_path / "history" / "positions_history.csv"

    ensure_portfolio_state_files(holdings_path, history_path)

    assert holdings_path.exists()
    assert history_path.exists()
    assert history_path.read_text(encoding="utf-8").startswith("date,ticker,action,price,shares,reason")


def test_append_positions_history(tmp_path: Path):
    history_path = tmp_path / "positions_history.csv"
    signals = build_action_signals(make_report(), {})

    append_positions_history(signals, history_path)

    content = history_path.read_text(encoding="utf-8")
    assert "BUY NOW" in content
    assert "AAA" in content


def test_portfolio_journal_generation(tmp_path: Path):
    history_path = tmp_path / "positions_history.csv"
    journal_path = tmp_path / "portfolio_journal.md"
    holdings = {}
    signals = build_action_signals(make_report(), holdings)
    append_positions_history(signals, history_path)

    write_portfolio_journal(holdings, signals, history_path, journal_path)

    content = journal_path.read_text(encoding="utf-8")
    assert "Current Holdings" in content
    assert "None" in content
    assert "Recent Signals" in content
    assert "Portfolio History" in content


def test_populated_holdings_file_loads_positions(tmp_path: Path):
    holdings_path = tmp_path / "current_holdings.csv"
    holdings_path.write_text("ticker,shares,avg_price\nAAA,4,80\nBBB,2,90\n", encoding="utf-8")

    holdings = load_current_holdings(holdings_path)

    assert sorted(holdings) == ["AAA", "BBB"]


def test_write_action_signal_report(tmp_path: Path):
    signals = build_action_signals(make_report(), {})
    output_path = tmp_path / "action_signal.md"

    write_action_signal_report(signals, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Manual Action Signal" in content
    assert "BUY NOW" in content
    assert "No Nordnet connection" in content
