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
    score: int
    signal: str
    reason: str
    entry_price: float
    stop_loss: float
    target_price: float
    expected_holding_period: str
    confidence_score: int


class WatchlistLike(Protocol):
    ticker: str
    name: str
    market: str


class RiskConfigLike(Protocol):
    stop_loss_pct: float
    take_profit_pct: float
    minimum_buy_score: int


class SignalConfigLike(Protocol):
    sell_momentum_threshold: float


def analyze_price_history(
    item: WatchlistLike,
    history: pd.DataFrame,
    risk_config: RiskConfigLike,
    signal_config: SignalConfigLike,
) -> StockAnalysis:
    if len(history) < 50:
        raise ValueError("At least 50 trading days are required")

    frame = history.copy()
    frame["SMA20"] = frame["Close"].rolling(window=20).mean()
    frame["SMA50"] = frame["Close"].rolling(window=50).mean()
    frame["Momentum30D"] = frame["Close"].pct_change(periods=30)
    frame["DailyReturn"] = frame["Close"].pct_change()

    latest = frame.dropna(subset=["SMA20", "SMA50", "Momentum30D"]).iloc[-1]
    volatility = float(frame["DailyReturn"].dropna().std() * np.sqrt(252))
    close = float(latest["Close"])
    sma20 = float(latest["SMA20"])
    sma50 = float(latest["SMA50"])
    momentum_30d = float(latest["Momentum30D"])
    score = calculate_stock_score(
        close=close,
        sma20=sma20,
        sma50=sma50,
        momentum_30d=momentum_30d,
        volatility=volatility,
    )
    signal, reason = classify_signal(
        close=close,
        sma20=sma20,
        sma50=sma50,
        momentum_30d=momentum_30d,
        score=score,
        risk_config=risk_config,
        signal_config=signal_config,
    )

    return StockAnalysis(
        ticker=item.ticker,
        name=item.name,
        market=item.market,
        close=close,
        sma20=sma20,
        sma50=sma50,
        momentum_30d=momentum_30d,
        volatility=volatility,
        score=score,
        signal=signal,
        reason=reason,
        entry_price=calculate_entry_price(close),
        stop_loss=calculate_stop_loss(close, risk_config.stop_loss_pct),
        target_price=calculate_target_price(close, risk_config.take_profit_pct),
        expected_holding_period=estimate_holding_period(score, volatility),
        confidence_score=calculate_confidence_score(score, volatility),
    )


def classify_signal(
    close: float,
    sma20: float,
    sma50: float,
    momentum_30d: float,
    score: int,
    risk_config: RiskConfigLike,
    signal_config: SignalConfigLike,
) -> tuple[str, str]:
    if (close < sma20 and close < sma50) or momentum_30d <= signal_config.sell_momentum_threshold:
        return "SELL", "Weakness: close below moving averages or momentum below configured threshold"

    if close > sma50 and sma20 > sma50 and score >= risk_config.minimum_buy_score:
        return "BUY", "Trend filter passed and score meets minimum buy threshold"

    return "HOLD", "Mixed trend or insufficient confirmation"


def calculate_stock_score(
    close: float,
    sma20: float,
    sma50: float,
    momentum_30d: float,
    volatility: float,
) -> int:
    trend_score = 0
    if close > sma20:
        trend_score += 15
    if close > sma50:
        trend_score += 15
    if sma20 > sma50:
        trend_score += 20

    momentum_score = clamp((momentum_30d + 0.10) / 0.30 * 30, 0, 30)
    volatility_score = clamp((0.50 - volatility) / 0.50 * 20, 0, 20)

    return int(round(clamp(trend_score + momentum_score + volatility_score, 0, 100)))


def calculate_entry_price(close: float) -> float:
    return round(close, 2)


def calculate_stop_loss(entry_price: float, stop_loss_pct: float) -> float:
    return round(entry_price * (1 - stop_loss_pct), 2)


def calculate_target_price(entry_price: float, take_profit_pct: float) -> float:
    return round(entry_price * (1 + take_profit_pct), 2)


def estimate_holding_period(score: int, volatility: float) -> str:
    if score >= 85 and volatility <= 0.25:
        return "4-8 weeks"
    if score >= 70:
        return "2-6 weeks"
    if score >= 50:
        return "1-4 weeks"
    return "Review only"


def calculate_confidence_score(score: int, volatility: float) -> int:
    volatility_penalty = clamp(volatility * 40, 0, 25)
    return int(round(clamp(score - volatility_penalty, 0, 100)))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
