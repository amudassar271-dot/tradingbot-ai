from datetime import datetime
from pathlib import Path
from typing import Protocol
import csv

from modules.risk import Allocation, PortfolioRules
from modules.strategy import StockAnalysis
from modules.news import NewsContext, combined_confidence


class ReportConfigLike(Protocol):
    schedule: str


def generate_daily_report(
    analyses: list[StockAnalysis],
    allocations: list[Allocation],
    rules: PortfolioRules,
    report_config: ReportConfigLike,
    errors: list[str],
    output_path: Path,
    news_contexts: dict[str, NewsContext] | None = None,
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
        f"- Portfolio size: {rules.capital_nok:,.0f} NOK",
        f"- Max positions: {rules.max_positions}",
        f"- Position sizing: {rules.position_sizing}",
        f"- Cash reserve: {rules.cash_reserve_pct:.1%}",
        f"- Max position size: {rules.max_position_pct:.1%}",
        f"- Stop loss: {rules.stop_loss_pct:.1%}",
        f"- Take profit: {rules.take_profit_pct:.1%}",
        f"- Minimum buy score: {rules.minimum_buy_score}",
        f"- Report schedule: {report_config.schedule}",
        f"- Leverage: {'allowed' if rules.allow_leverage else 'not allowed'}",
        f"- Derivatives: {'allowed' if rules.allow_derivatives else 'not allowed'}",
        f"- Automatic trading: {'allowed' if rules.allow_automatic_trading else 'not allowed'}",
        "",
        "## Suggested Manual Allocation",
        "",
    ]

    if allocations:
        lines.extend([
            "| Ticker | Signal | Score | Amount | Weight | Entry | Stop | Target | Risk | Reward | Holding | Confidence | Note |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
        ])
        for allocation in allocations:
            lines.append(
                f"| {allocation.ticker} | {allocation.signal} | {allocation.score} | "
                f"{allocation.suggested_amount_nok:,.2f} NOK | {allocation.portfolio_weight:.2%} | "
                f"{allocation.entry_price:,.2f} | {allocation.stop_loss:,.2f} | "
                f"{allocation.target_price:,.2f} | {allocation.risk_amount_nok:,.2f} NOK | "
                f"{allocation.reward_amount_nok:,.2f} NOK | {allocation.expected_holding_period} | "
                f"{allocation.confidence_score} | {allocation.note} |"
            )
    else:
        lines.append("No BUY candidates passed the strategy rules today.")

    lines.extend([
        "",
        "## Signals",
        "",
        "| Ticker | Name | Market | Close | SMA20 | SMA50 | 30D Momentum | Volatility | Score | Confidence | Entry | Stop | Target | Holding | Signal | Reason |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ])

    for analysis in sorted(analyses, key=lambda item: (signal_rank(item.signal), -item.score)):
        lines.append(
            f"| {analysis.ticker} | {analysis.name} | {analysis.market} | "
            f"{analysis.close:,.2f} | {analysis.sma20:,.2f} | {analysis.sma50:,.2f} | "
            f"{analysis.momentum_30d:.2%} | {analysis.volatility:.2%} | "
            f"{analysis.score} | {analysis.confidence_score} | {analysis.entry_price:,.2f} | "
            f"{analysis.stop_loss:,.2f} | {analysis.target_price:,.2f} | "
            f"{analysis.expected_holding_period} | "
            f"{analysis.signal} | {analysis.reason} |"
        )

    if news_contexts:
        lines.extend([
            "",
            "## News Context",
            "",
            "News adjusts confidence context only. It does not create BUY signals.",
            "",
            "| Ticker | Technical Score | News Score | Combined Confidence | Top Headlines | Explanation |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ])
        for analysis in sorted(analyses, key=lambda item: item.ticker):
            context = news_contexts.get(analysis.ticker)
            if context is None:
                news_score = 0
                headlines = "No news found"
                explanation = "No recent ticker news found from yfinance."
            else:
                news_score = context.news_score
                headlines = format_headlines(context)
                explanation = context.explanation
            lines.append(
                f"| {analysis.ticker} | {analysis.score} | {news_score} | "
                f"{combined_confidence(analysis.confidence_score, news_score)} | "
                f"{headlines} | {explanation} |"
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


def append_portfolio_history(
    analyses: list[StockAnalysis],
    allocations: list[Allocation],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    allocation_by_ticker = {allocation.ticker: allocation for allocation in allocations}
    fieldnames = [
        "run_date",
        "ticker",
        "name",
        "market",
        "close",
        "score",
        "confidence",
        "signal",
        "suggested_allocation",
        "stop_loss",
        "target_price",
        "holding_period",
    ]
    file_exists = output_path.exists()
    run_date = datetime.now().strftime("%Y-%m-%d")

    with output_path.open("a", encoding="utf-8", newline="") as history_file:
        writer = csv.DictWriter(history_file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for analysis in sorted(analyses, key=lambda item: item.ticker):
            allocation = allocation_by_ticker.get(analysis.ticker)
            writer.writerow({
                "run_date": run_date,
                "ticker": analysis.ticker,
                "name": analysis.name,
                "market": analysis.market,
                "close": round(analysis.close, 4),
                "score": analysis.score,
                "confidence": analysis.confidence_score,
                "signal": analysis.signal,
                "suggested_allocation": allocation.suggested_amount_nok if allocation else 0,
                "stop_loss": analysis.stop_loss,
                "target_price": analysis.target_price,
                "holding_period": analysis.expected_holding_period,
            })


def signal_rank(signal: str) -> int:
    order = {"BUY": 0, "HOLD": 1, "SELL": 2}
    return order.get(signal, 99)


def format_headlines(context: NewsContext) -> str:
    if not context.headlines:
        return "No news found"
    return "<br>".join(headline.title for headline in context.headlines[:3])
