from types import SimpleNamespace

import pandas as pd

from modules.strategy import analyze_price_history, calculate_stock_score, classify_signal


RISK_CONFIG = SimpleNamespace(
    stop_loss_pct=0.08,
    take_profit_pct=0.16,
    minimum_buy_score=75,
)
SIGNAL_CONFIG = SimpleNamespace(sell_momentum_threshold=-0.08)


def test_classify_signal_buy():
    signal, _ = classify_signal(
        close=110,
        sma20=105,
        sma50=100,
        momentum_30d=0.05,
        score=80,
        risk_config=RISK_CONFIG,
        signal_config=SIGNAL_CONFIG,
    )

    assert signal == "BUY"


def test_classify_signal_sell_on_negative_momentum():
    signal, _ = classify_signal(
        close=105,
        sma20=100,
        sma50=95,
        momentum_30d=-0.10,
        score=80,
        risk_config=RISK_CONFIG,
        signal_config=SIGNAL_CONFIG,
    )

    assert signal == "SELL"


def test_calculate_stock_score_is_bounded():
    score = calculate_stock_score(close=110, sma20=105, sma50=100, momentum_30d=0.05, volatility=0.20)

    assert 0 <= score <= 100


def test_analyze_price_history_returns_expected_fields():
    history = pd.DataFrame({"Close": [100 + index for index in range(60)]})
    item = SimpleNamespace(ticker="TEST", name="Test Company", market="US")

    analysis = analyze_price_history(item, history, RISK_CONFIG, SIGNAL_CONFIG)

    assert analysis.ticker == "TEST"
    assert analysis.signal in {"BUY", "HOLD", "SELL"}
    assert analysis.sma20 > 0
    assert analysis.sma50 > 0
    assert 0 <= analysis.score <= 100
    assert 0 <= analysis.confidence_score <= 100
    assert analysis.stop_loss < analysis.entry_price < analysis.target_price
