from datetime import datetime
from pathlib import Path

from modules.risk import Allocation, PortfolioRules
from modules.strategy import StockAnalysis


def generate_daily_report(
    analyses: list[StockAnalysis],
    allocations: list[Allocation],
    rules: PortfolioRules,
    errors: list[str],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# Daily Stock Analysis Report",
        "",
        f"Generated: {now}",
        "",
        "## Constraints",
        "",
        f"- Portfolio size: {rules.portfolio_size_nok:,.0f} NOK",
        f"- Max positions: {rules.max_positions}",
        f"- Leverage: {'allowed' if rules.allow_leverage else 'not allowed'}",
        f"- Derivatives: {'allowed' if rules.allow_derivatives else 'not allowed'}",
        f"- Automatic trading: {'allowed' if rules.allow_automatic_trading else 'not allowed'}",
        "",
        "## Suggested Manual Allocation",
        "",
    ]

    if allocations:
        lines.extend([
            "| Ticker | Signal | Suggested amount | Note |",
            "| --- | --- | ---: | --- |",
        ])
        for allocation in allocations:
            lines.append(
                f"| {allocation.ticker} | {allocation.signal} | "
                f"{allocation.suggested_amount_nok:,.2f} NOK | {allocation.note} |"
            )
    else:
        lines.append("No BUY candidates passed the strategy rules today.")

    lines.extend([
        "",
        "## Signals",
        "",
        "| Ticker | Name | Market | Close | SMA20 | SMA50 | 30D Momentum | Volatility | Signal | Reason |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ])

    for analysis in sorted(analyses, key=lambda item: signal_rank(item.signal)):
        lines.append(
            f"| {analysis.ticker} | {analysis.name} | {analysis.market} | "
            f"{analysis.close:,.2f} | {analysis.sma20:,.2f} | {analysis.sma50:,.2f} | "
            f"{analysis.momentum_30d:.2%} | {analysis.volatility:.2%} | "
            f"{analysis.signal} | {analysis.reason} |"
        )

    if errors:
        lines.extend([
            "",
            "## Data Issues",
            "",
        ])
        lines.extend(f"- {error}" for error in errors)

    lines.extend([
        "",
        "## Disclaimer",
        "",
        "This report is for research only and is not financial advice. All actions require manual review.",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def signal_rank(signal: str) -> int:
    order = {"BUY": 0, "HOLD": 1, "SELL": 2}
    return order.get(signal, 99)
