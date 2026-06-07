import argparse
from pathlib import Path

from modules.ai_analyst import analyze_watchlist_news, write_ai_analysis_report
from modules.action_signal import (
    append_positions_history,
    build_action_signals,
    ensure_portfolio_state_files,
    load_current_holdings,
    write_action_signal_report,
    write_portfolio_journal,
)
from modules.backtest import (
    run_backtest_comparison,
    run_capital_comparison,
    write_backtest_comparison_report,
    write_capital_comparison_report,
)
from modules.benchmark import run_benchmark_comparison, write_benchmark_report
from modules.config import load_config
from modules.market_data import fetch_price_history, load_watchlist
from modules.momentum_report import run_momentum_strategy_comparison, write_momentum_strategy_report
from modules.momentum_stress import run_momentum_stress_test, write_momentum_stress_test_report
from modules.news import fetch_news_for_watchlist, write_news_report
from modules.openai_analyst import analyze_primary_strategy_with_openai, write_openai_analysis_report
from modules.report import append_portfolio_history, generate_daily_report
from modules.risk import PortfolioRules, build_allocation_plan
from modules.strategy_report import build_primary_strategy_report, write_strategy_report
from modules.strategy import analyze_price_history


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.yaml"
LOG_PATH = BASE_DIR / "logs" / "app.log"
PORTFOLIO_HISTORY_PATH = BASE_DIR / "history" / "portfolio_history.csv"
AI_ANALYSIS_PATH = BASE_DIR / "reports" / "ai_analysis.md"
CAPITAL_COMPARISON_PATH = BASE_DIR / "reports" / "capital_comparison_report.md"
BENCHMARK_REPORT_PATH = BASE_DIR / "reports" / "benchmark_report.md"
MOMENTUM_STRATEGY_REPORT_PATH = BASE_DIR / "reports" / "momentum_strategy_report.md"
MOMENTUM_STRESS_TEST_REPORT_PATH = BASE_DIR / "reports" / "momentum_stress_test_report.md"
STRATEGY_REPORT_PATH = BASE_DIR / "reports" / "strategy_report.md"
OPENAI_ANALYSIS_PATH = BASE_DIR / "reports" / "openai_analysis.md"
OPENAI_CACHE_PATH = BASE_DIR / "data" / "openai_analysis_cache.json"
ACTION_SIGNAL_PATH = BASE_DIR / "reports" / "action_signal.md"
CURRENT_HOLDINGS_PATH = BASE_DIR / "data" / "current_holdings.csv"
POSITIONS_HISTORY_PATH = BASE_DIR / "history" / "positions_history.csv"
PORTFOLIO_JOURNAL_PATH = BASE_DIR / "reports" / "portfolio_journal.md"


def run() -> int:
    parser = argparse.ArgumentParser(description="Research-only stock analysis bot")
    parser.add_argument("--backtest", action="store_true", help="Run historical backtest")
    parser.add_argument("--capital-comparison", action="store_true", help="Run capital scenario comparison")
    parser.add_argument("--benchmark", action="store_true", help="Run passive benchmark comparison")
    parser.add_argument("--momentum-strategy", action="store_true", help="Run momentum portfolio strategy comparison")
    parser.add_argument("--momentum-stress-test", action="store_true", help="Run momentum portfolio stress test")
    parser.add_argument("--strategy-report", action="store_true", help="Generate primary strategy report")
    parser.add_argument("--ai-analysis", action="store_true", help="Generate OpenAI market analysis for selected momentum candidates")
    parser.add_argument("--action-signal", action="store_true", help="Generate manual action signal report")
    args = parser.parse_args()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ensure_portfolio_state_files(CURRENT_HOLDINGS_PATH, POSITIONS_HISTORY_PATH)

    config = load_config(CONFIG_PATH, BASE_DIR)
    watchlist = load_watchlist(config.market_data.watchlist_path)

    if args.backtest:
        results = run_backtest_comparison(watchlist, config)
        write_backtest_comparison_report(results, config.backtest.output_path)
        print(f"Backtest report written to {config.backtest.output_path}")
        return 0

    if args.capital_comparison:
        results = run_capital_comparison(watchlist, config, [20_000, 30_000])
        write_capital_comparison_report(results, CAPITAL_COMPARISON_PATH)
        print(f"Capital comparison report written to {CAPITAL_COMPARISON_PATH}")
        return 0

    if args.benchmark:
        bot_results = run_capital_comparison(watchlist, config, [20_000, 30_000])
        benchmark_results = run_benchmark_comparison(watchlist, config, [20_000, 30_000], bot_results)
        write_benchmark_report(benchmark_results, BENCHMARK_REPORT_PATH)
        print(f"Benchmark report written to {BENCHMARK_REPORT_PATH}")
        return 0

    if args.momentum_strategy:
        results = run_momentum_strategy_comparison(watchlist, config, [20_000, 30_000])
        write_momentum_strategy_report(results, MOMENTUM_STRATEGY_REPORT_PATH)
        print(f"Momentum strategy report written to {MOMENTUM_STRATEGY_REPORT_PATH}")
        return 0

    if args.momentum_stress_test:
        results = run_momentum_stress_test(watchlist, config)
        write_momentum_stress_test_report(results, MOMENTUM_STRESS_TEST_REPORT_PATH)
        print(f"Momentum stress test report written to {MOMENTUM_STRESS_TEST_REPORT_PATH}")
        return 0

    if args.strategy_report:
        report = build_primary_strategy_report(watchlist, config)
        write_strategy_report(report, STRATEGY_REPORT_PATH)
        print(f"Strategy report written to {STRATEGY_REPORT_PATH}")
        return 0

    if args.ai_analysis:
        strategy_report = build_primary_strategy_report(watchlist, config)
        selected_tickers = {candidate.ticker for candidate in strategy_report.candidates}
        selected_watchlist = [item for item in watchlist if item.ticker in selected_tickers]
        news_contexts = fetch_news_for_watchlist(selected_watchlist, config.news)
        analyses = analyze_primary_strategy_with_openai(strategy_report, news_contexts, OPENAI_CACHE_PATH)
        write_openai_analysis_report(analyses, OPENAI_ANALYSIS_PATH)
        print(f"OpenAI analysis report written to {OPENAI_ANALYSIS_PATH}")
        return 0

    if args.action_signal:
        strategy_report = build_primary_strategy_report(watchlist, config)
        current_holdings = load_current_holdings(CURRENT_HOLDINGS_PATH)
        current_prices = fetch_current_prices_for_holdings(current_holdings)
        signals = build_action_signals(strategy_report, current_holdings, current_prices)
        write_action_signal_report(signals, ACTION_SIGNAL_PATH)
        append_positions_history(signals, POSITIONS_HISTORY_PATH)
        write_portfolio_journal(current_holdings, signals, POSITIONS_HISTORY_PATH, PORTFOLIO_JOURNAL_PATH)
        print(f"Action signal report written to {ACTION_SIGNAL_PATH}")
        print(f"Portfolio journal written to {PORTFOLIO_JOURNAL_PATH}")
        return 0

    analyses = []
    errors = []

    for item in watchlist:
        try:
            history = fetch_price_history(item.ticker, months=config.market_data.history_months)
            analyses.append(analyze_price_history(item, history, config.risk, config.signals))
        except Exception as exc:
            message = f"{item.ticker}: {exc}"
            errors.append(message)
            with LOG_PATH.open("a", encoding="utf-8") as log_file:
                log_file.write(message + "\n")

    rules = PortfolioRules.from_config(config.portfolio, config.risk, config.trading)
    allocation_plan = build_allocation_plan(analyses, rules)
    news_contexts = fetch_news_for_watchlist(watchlist, config.news)
    write_news_report(news_contexts, config.news.output_path)
    ai_analyses = analyze_watchlist_news(analyses, news_contexts)
    write_ai_analysis_report(ai_analyses, AI_ANALYSIS_PATH)
    generate_daily_report(
        analyses,
        allocation_plan,
        rules,
        config.report,
        errors,
        config.report.output_path,
        news_contexts,
    )
    append_portfolio_history(analyses, allocation_plan, PORTFOLIO_HISTORY_PATH)

    print(f"Report written to {config.report.output_path}")
    print(f"Portfolio history appended to {PORTFOLIO_HISTORY_PATH}")
    if errors:
        print(f"Completed with {len(errors)} data issue(s). See {LOG_PATH}.")
    return 0


def fetch_current_prices_for_holdings(current_holdings) -> dict[str, float]:
    prices = {}
    for ticker, holding in current_holdings.items():
        try:
            history = fetch_price_history(ticker, months=1)
            prices[ticker] = float(history.iloc[-1]["Close"])
        except Exception:
            prices[ticker] = holding.avg_price
    return prices


if __name__ == "__main__":
    raise SystemExit(run())
