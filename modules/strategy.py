from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StockAnalysis:
    ticker: str
    name: str
    market: str
    close: float
    sma20: float
    sma50: float
    momentum_30d: float
    volatility: float
    signal: str
    reason: str


class WatchlistLike(Protocol):
    ticker: str
    name: str
    market: str


def analyze_price_history(item: WatchlistLike, history: pd.DataFrame) -> StockAnalysis:
    if len(history) < 50:
        raise ValueError("At least 50 trading days are required")

    frame = history.copy()
    frame["SMA20"] = frame["Close"].rolling(window=20).mean()
    frame["SMA50"] = frame["Close"].rolling(window=50).mean()
    frame["Momentum30D"] = frame["Close"].pct_change(periods=30)
    frame["DailyReturn"] = frame["Close"].pct_change()

    latest = frame.dropna(subset=["SMA20", "SMA50", "Momentum30D"]).iloc[-1]
    volatility = float(frame["DailyReturn"].dropna().std() * np.sqrt(252))
    signal, reason = classify_signal(
        close=float(latest["Close"]),
        sma20=float(latest["SMA20"]),
        sma50=float(latest["SMA50"]),
        momentum_30d=float(latest["Momentum30D"]),
    )

    return StockAnalysis(
        ticker=item.ticker,
        name=item.name,
        market=item.market,
        close=float(latest["Close"]),
        sma20=float(latest["SMA20"]),
        sma50=float(latest["SMA50"]),
        momentum_30d=float(latest["Momentum30D"]),
        volatility=volatility,
        signal=signal,
        reason=reason,
    )


def classify_signal(close: float, sma20: float, sma50: float, momentum_30d: float) -> tuple[str, str]:
    if close > sma20 > sma50 and momentum_30d > 0:
        return "BUY", "Uptrend: close above SMA20/SMA50 with positive 30-day momentum"

    if (close < sma20 and close < sma50) or momentum_30d <= -0.08:
        return "SELL", "Weakness: close below moving averages or momentum below -8%"

    return "HOLD", "Mixed trend or insufficient confirmation"
