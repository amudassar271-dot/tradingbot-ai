from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class WatchlistItem:
    ticker: str
    name: str
    market: str


DEFAULT_WATCHLIST = [
    WatchlistItem("EQNR.OL", "Equinor", "Oslo Bors"),
    WatchlistItem("DNB.OL", "DNB Bank", "Oslo Bors"),
    WatchlistItem("TEL.OL", "Telenor", "Oslo Bors"),
    WatchlistItem("AAPL", "Apple", "US"),
    WatchlistItem("MSFT", "Microsoft", "US"),
    WatchlistItem("NVDA", "NVIDIA", "US"),
]


def load_watchlist(path: Path) -> list[WatchlistItem]:
    if not path.exists():
        return DEFAULT_WATCHLIST

    frame = pd.read_csv(path)
    required_columns = {"ticker", "name", "market"}
    missing = required_columns.difference(frame.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Watchlist is missing required column(s): {missing_text}")

    items = []
    for row in frame.itertuples(index=False):
        ticker = str(row.ticker).strip()
        if not ticker:
            continue
        items.append(
            WatchlistItem(
                ticker=ticker,
                name=str(row.name).strip() or ticker,
                market=str(row.market).strip() or "Unknown",
            )
        )

    if not items:
        raise ValueError("Watchlist does not contain any tickers")
    return items


def fetch_price_history(ticker: str, months: int = 6) -> pd.DataFrame:
    history = yf.download(
        ticker,
        period=f"{months}mo",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if history.empty:
        raise ValueError("No price history returned")

    if isinstance(history.columns, pd.MultiIndex):
        history.columns = history.columns.get_level_values(0)

    required_columns = {"Close"}
    missing = required_columns.difference(history.columns)
    if missing:
        raise ValueError("Price history is missing close prices")

    return history.dropna(subset=["Close"]).copy()
