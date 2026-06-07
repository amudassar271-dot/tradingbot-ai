from dataclasses import dataclass
from datetime import date
from pathlib import Path
import csv

from modules.strategy_report import PrimaryStrategyReport, StrategyCandidate


@dataclass(frozen=True)
class CurrentHolding:
    ticker: str
    shares: float
    avg_price: float


@dataclass(frozen=True)
class ActionSignal:
    action: str
    ticker: str = ""
    company: str = ""
    current_price: float = 0.0
    suggested_nok: float = 0.0
    estimated_shares: float = 0.0
    shares_to_sell: float = 0.0
    estimated_value: float = 0.0
    commission: float = 0.0
    reason: str = ""


def load_current_holdings(path: Path) -> dict[str, CurrentHolding]:
    ensure_current_holdings_file(path)
    if not path.exists():
        return {}

    holdings = {}
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        required = {"ticker", "shares", "avg_price"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError("current_holdings.csv must contain ticker,shares,avg_price")
        for row in reader:
            ticker = str(row["ticker"]).strip()
            if not ticker:
                continue
            holdings[ticker] = CurrentHolding(
                ticker=ticker,
                shares=float(row["shares"]),
                avg_price=float(row["avg_price"]),
            )
    return holdings


def ensure_current_holdings_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ticker,shares,avg_price\n", encoding="utf-8")


def ensure_positions_history_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("date,ticker,action,price,shares,reason\n", encoding="utf-8")


def ensure_portfolio_state_files(holdings_path: Path, positions_history_path: Path) -> None:
    ensure_current_holdings_file(holdings_path)
    ensure_positions_history_file(positions_history_path)


def build_action_signals(
    strategy_report: PrimaryStrategyReport,
    current_holdings: dict[str, CurrentHolding],
    current_prices: dict[str, float] | None = None,
) -> list[ActionSignal]:
    target_by_ticker = {candidate.ticker: candidate for candidate in strategy_report.candidates}
    current_prices = current_prices or {}
    signals: list[ActionSignal] = []

    for ticker, holding in sorted(current_holdings.items()):
        candidate = target_by_ticker.get(ticker)
        if candidate is None:
            current_price = current_prices.get(ticker, holding.avg_price)
            signals.append(ActionSignal(
                action="SELL NOW",
                ticker=ticker,
                company=ticker,
                current_price=current_price,
                shares_to_sell=holding.shares,
                estimated_value=holding.shares * current_price,
                commission=strategy_report.commission_nok,
                reason="Stock is no longer selected by primary momentum strategy.",
            ))
        else:
            signals.append(ActionSignal(
                action="HOLD",
                ticker=ticker,
                company=candidate.name,
                current_price=candidate.entry_price,
                shares_to_sell=holding.shares,
                reason="Still selected by primary momentum strategy.",
            ))

    for ticker, candidate in sorted(target_by_ticker.items()):
        if ticker in current_holdings:
            continue
        signals.append(build_buy_signal(candidate, strategy_report.commission_nok))

    if not any(signal.action in {"BUY NOW", "SELL NOW"} for signal in signals):
        signals.append(ActionSignal(action="NO ACTION TODAY"))

    return signals


def build_buy_signal(candidate: StrategyCandidate, commission: float) -> ActionSignal:
    estimated_shares = candidate.allocation_nok / candidate.entry_price if candidate.entry_price else 0
    return ActionSignal(
        action="BUY NOW",
        ticker=candidate.ticker,
        company=candidate.name,
        current_price=candidate.entry_price,
        suggested_nok=candidate.allocation_nok,
        estimated_shares=estimated_shares,
        commission=commission,
        reason="Manual review required.",
    )


def write_action_signal_report(signals: list[ActionSignal], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Manual Action Signal",
        "",
        "Human-readable instructions only. No trades are placed. No Nordnet connection is used.",
        "",
    ]

    for signal in signals:
        if signal.action == "BUY NOW":
            lines.extend([
                "## BUY NOW",
                f"Ticker: {signal.ticker}",
                f"Company: {signal.company}",
                f"Current price: {signal.current_price:,.2f}",
                f"Suggested NOK amount: {signal.suggested_nok:,.2f}",
                f"Estimated shares: {signal.estimated_shares:.4f}",
                f"Commission: {signal.commission:,.2f} NOK",
                "Manual review required.",
                "",
            ])
        elif signal.action == "SELL NOW":
            lines.extend([
                "## SELL NOW",
                f"Ticker: {signal.ticker}",
                f"Company: {signal.company}",
                f"Current price: {signal.current_price:,.2f}",
                f"Shares to sell: {signal.shares_to_sell:.4f}",
                f"Estimated NOK value: {signal.estimated_value:,.2f}",
                f"Commission: {signal.commission:,.2f} NOK",
                f"Reason: {signal.reason}",
                "",
            ])
        elif signal.action == "HOLD":
            lines.extend([
                "## HOLD",
                f"Ticker: {signal.ticker}",
                f"Current price: {signal.current_price:,.2f}",
                f"Shares: {signal.shares_to_sell:.4f}",
                f"Reason: {signal.reason}",
                "",
            ])
        elif signal.action == "NO ACTION TODAY":
            lines.extend([
                "## NO ACTION TODAY",
                "",
            ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def append_positions_history(signals: list[ActionSignal], output_path: Path, run_date: date | None = None) -> None:
    ensure_positions_history_file(output_path)
    current_date = (run_date or date.today()).isoformat()
    with output_path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        for signal in signals:
            if signal.action not in {"BUY NOW", "SELL NOW", "HOLD"}:
                continue
            writer.writerow([
                current_date,
                signal.ticker,
                signal.action,
                f"{signal.current_price:.4f}",
                f"{history_signal_shares(signal):.6f}",
                signal.reason,
            ])


def history_signal_shares(signal: ActionSignal) -> float:
    if signal.action == "BUY NOW":
        return signal.estimated_shares
    return signal.shares_to_sell


def write_portfolio_journal(
    current_holdings: dict[str, CurrentHolding],
    signals: list[ActionSignal],
    positions_history_path: Path,
    output_path: Path,
) -> None:
    ensure_positions_history_file(positions_history_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    history_rows = read_positions_history_rows(positions_history_path)
    lines = [
        "# Portfolio Journal",
        "",
        "## Current Holdings",
        "",
    ]

    if current_holdings:
        lines.extend([
            "| Ticker | Shares | Avg price |",
            "| --- | ---: | ---: |",
        ])
        for holding in sorted(current_holdings.values(), key=lambda item: item.ticker):
            lines.append(f"| {holding.ticker} | {holding.shares:.4f} | {holding.avg_price:,.2f} |")
    else:
        lines.append("None")

    lines.extend([
        "",
        "## Recent Signals",
        "",
    ])
    signal_rows = [signal for signal in signals if signal.action != "NO ACTION TODAY"]
    if signal_rows:
        lines.extend(format_signal_table(signal_rows))
    else:
        lines.append("NO ACTION TODAY")

    lines.extend([
        "",
        "## Recent Buys",
        "",
    ])
    lines.extend(format_history_action_rows(history_rows, "BUY NOW"))

    lines.extend([
        "",
        "## Recent Sells",
        "",
    ])
    lines.extend(format_history_action_rows(history_rows, "SELL NOW"))

    lines.extend([
        "",
        "## Strategy Changes",
        "",
        "Primary strategy remains momentum_portfolio. This journal records manual action signals only; it does not place trades.",
        "",
        "## Portfolio History",
        "",
    ])
    if history_rows:
        lines.extend(format_history_table(history_rows[-20:]))
    else:
        lines.append("No position history yet.")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def read_positions_history_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def format_signal_table(signals: list[ActionSignal]) -> list[str]:
    lines = [
        "| Action | Ticker | Price | Shares | Reason |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for signal in signals:
        lines.append(
            f"| {signal.action} | {signal.ticker} | {signal.current_price:,.2f} | "
            f"{history_signal_shares(signal):.4f} | {signal.reason} |"
        )
    return lines


def format_history_action_rows(rows: list[dict[str, str]], action: str) -> list[str]:
    filtered = [row for row in rows if row.get("action") == action][-10:]
    if not filtered:
        return ["None"]
    return format_history_table(filtered)


def format_history_table(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| Date | Ticker | Action | Price | Shares | Reason |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('date', '')} | {row.get('ticker', '')} | {row.get('action', '')} | "
            f"{row.get('price', '')} | {row.get('shares', '')} | {row.get('reason', '')} |"
        )
    return lines
