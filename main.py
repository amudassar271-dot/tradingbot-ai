from pathlib import Path

from modules.market_data import fetch_price_history, load_watchlist
from modules.report import generate_daily_report
from modules.risk import PortfolioRules, build_allocation_plan
from modules.strategy import analyze_price_history


BASE_DIR = Path(__file__).resolve().parent
WATCHLIST_PATH = BASE_DIR / "data" / "watchlist.csv"
REPORT_PATH = BASE_DIR / "reports" / "daily_report.md"
LOG_PATH = BASE_DIR / "logs" / "app.log"


def run() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    watchlist = load_watchlist(WATCHLIST_PATH)
    analyses = []
    errors = []

    for item in watchlist:
        try:
            history = fetch_price_history(item.ticker, months=6)
            analyses.append(analyze_price_history(item, history))
        except Exception as exc:
            message = f"{item.ticker}: {exc}"
            errors.append(message)
            with LOG_PATH.open("a", encoding="utf-8") as log_file:
                log_file.write(message + "\n")

    rules = PortfolioRules(portfolio_size_nok=20_000, max_positions=5)
    allocation_plan = build_allocation_plan(analyses, rules)
    generate_daily_report(analyses, allocation_plan, rules, errors, REPORT_PATH)

    print(f"Report written to {REPORT_PATH}")
    if errors:
        print(f"Completed with {len(errors)} data issue(s). See {LOG_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
