from types import SimpleNamespace

import pandas as pd

from modules.strategy import analyze_price_history, classify_signal


def test_classify_signal_buy():
    signal, _ = classify_signal(close=110, sma20=105, sma50=100, momentum_30d=0.05)

    assert signal == "BUY"


def test_classify_signal_sell_on_negative_momentum():
    signal, _ = classify_signal(close=105, sma20=100, sma50=95, momentum_30d=-0.10)

    assert signal == "SELL"


def test_analyze_price_history_returns_expected_fields():
    history = pd.DataFrame({"Close": [100 + index for index in range(60)]})
    item = SimpleNamespace(ticker="TEST", name="Test Company", market="US")

    analysis = analyze_price_history(item, history)

    assert analysis.ticker == "TEST"
    assert analysis.signal in {"BUY", "HOLD", "SELL"}
    assert analysis.sma20 > 0
    assert analysis.sma50 > 0
