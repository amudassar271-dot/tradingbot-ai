from pathlib import Path

import pandas as pd

from modules.momentum_stress import (
    MomentumStressRow,
    build_period_histories,
    build_stress_interpretation,
    risk_adjusted_score,
    write_momentum_stress_test_report,
)


def make_history(length: int):
    dates = pd.date_range("2024-01-01", periods=length, freq="B")
    return pd.DataFrame({"Close": range(100, 100 + length)}, index=dates)


def test_build_period_histories_creates_available_rolling_windows():
    histories = {"AAA": make_history(260), "QQQ": make_history(260)}

    periods = build_period_histories(histories)

    assert "last_3_months" in periods
    assert "last_6_months" in periods
    assert "last_12_months" in periods
    assert "last_24_months" in periods
    assert len(periods["last_3_months"]["AAA"]) == 63


def test_risk_adjusted_score_uses_drawdown_penalty():
    higher_return_higher_risk = MomentumStressRow("last_12_months", 3, "monthly", 0.08, 0, 0.20, -0.20, 10, 290, 24000)
    lower_return_lower_risk = MomentumStressRow("last_12_months", 3, "monthly", 0.08, 0, 0.12, -0.05, 10, 290, 22400)

    assert risk_adjusted_score(lower_return_lower_risk) > risk_adjusted_score(higher_return_higher_risk)


def test_write_momentum_stress_test_report(tmp_path: Path):
    rows = [
        MomentumStressRow("last_12_months", 3, "monthly", 0.08, 0, 0.20, -0.10, 12, 348, 24000),
        MomentumStressRow("comparison_24_months", 3, "monthly", 0.08, 0, 0.20, -0.10, 12, 348, 24000, "momentum_portfolio", "comparison"),
        MomentumStressRow("comparison_24_months", 3, "monthly", 0.08, 0, 0.15, -0.09, 10, 290, 23000, "momentum_portfolio_no_nvda", "comparison"),
        MomentumStressRow("comparison_24_months", 0, "buy_hold", 0, 0, 0.10, -0.08, 2, 58, 22000, "Buy and hold QQQ", "comparison"),
    ]
    output_path = tmp_path / "momentum_stress_test_report.md"

    write_momentum_stress_test_report(rows, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Momentum Stress Test Report" in content
    assert "Sensitivity Matrix" in content
    assert "momentum_portfolio_no_nvda" in content
    assert "Best net return" in content


def test_stress_interpretation_mentions_nvda_dependency():
    rows = [
        MomentumStressRow("last_12_months", 3, "monthly", 0.08, 0, 0.20, -0.10, 12, 348, 24000),
        MomentumStressRow("comparison_24_months", 3, "monthly", 0.08, 0, 0.20, -0.10, 12, 348, 24000, "momentum_portfolio", "comparison"),
        MomentumStressRow("comparison_24_months", 3, "monthly", 0.08, 0, -0.05, -0.09, 10, 290, 19000, "momentum_portfolio_no_nvda", "comparison"),
    ]

    interpretation = build_stress_interpretation(rows)

    assert "NVDA dependency check" in interpretation
    assert "meaningful dependence" in interpretation
