from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from modules.backtest import BacktestResult
from modules.benchmark import (
    BenchmarkResult,
    build_benchmark_interpretation,
    build_single_asset_benchmark,
    calculate_price_drawdown,
    write_benchmark_report,
)


def make_config():
    return SimpleNamespace(transaction_costs=SimpleNamespace(fixed_nok=29))


def test_single_asset_benchmark_deducts_buy_and_sell_commission():
    histories = {
        "AAA": pd.DataFrame({"Close": [100, 110]}),
    }

    result = build_single_asset_benchmark("Buy and hold AAA", "AAA", histories, 10000, make_config())

    assert result.number_of_trades == 2
    assert result.total_commissions == 58
    assert round(result.ending_capital, 2) == 10939.1


def test_calculate_price_drawdown():
    drawdown = calculate_price_drawdown(pd.Series([100, 120, 90, 110]))

    assert round(drawdown, 4) == -0.25


def test_benchmark_interpretation_says_bot_did_not_add_value():
    results = [
        BenchmarkResult("Bot: robust_current", 20000, 0.01, 0.01, 20200, -0.05, 2, 58, "bot"),
        BenchmarkResult("Buy and hold AAA", 20000, 0.10, 0.09, 21800, -0.10, 2, 58, "benchmark"),
    ]

    interpretation = build_benchmark_interpretation(results)

    assert "did not add value" in interpretation


def test_write_benchmark_report(tmp_path: Path):
    output_path = tmp_path / "benchmark_report.md"
    results = [
        BenchmarkResult("Bot: robust_current", 20000, 0.01, 0.01, 20200, -0.05, 2, 58, "bot"),
        BenchmarkResult("Buy and hold AAA", 20000, 0.10, 0.09, 21800, -0.10, 2, 58, "benchmark"),
    ]

    write_benchmark_report(results, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "Benchmark Comparison Report" in content
    assert "Strategy / Benchmark" in content
    assert "Did not" not in content
