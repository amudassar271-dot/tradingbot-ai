from pathlib import Path
from types import SimpleNamespace

from modules.ai_analyst import (
    AIAnalysis,
    analyze_ticker_news,
    classify_ai_sentiment,
    find_flags,
    write_ai_analysis_report,
)
from modules.news import NewsContext, NewsItem


def make_analysis(score=80, confidence=72, signal="HOLD"):
    return SimpleNamespace(
        ticker="AAA",
        score=score,
        confidence_score=confidence,
        signal=signal,
    )


def test_find_risk_flags():
    flags = find_flags("Company faces lawsuit and supply chain pressure", ["lawsuit", "supply chain"])

    assert flags == ["lawsuit", "supply chain"]


def test_find_opportunity_flags():
    flags = find_flags("New contract supports growth", ["contract", "growth"])

    assert flags == ["contract", "growth"]


def test_classify_ai_sentiment_bullish():
    context = NewsContext("AAA", 10, [], "positive")

    sentiment = classify_ai_sentiment(make_analysis(score=80), [], ["contract", "growth"], context)

    assert sentiment == "Bullish"


def test_classify_ai_sentiment_bearish():
    context = NewsContext("AAA", -10, [], "negative")

    sentiment = classify_ai_sentiment(make_analysis(score=45), ["lawsuit"], [], context)

    assert sentiment == "Bearish"


def test_analyze_ticker_news_does_not_return_signal():
    headlines = [
        NewsItem("AAA", "Company wins contract amid strong growth", "Publisher", "", "2026-01-01", "positive"),
    ]
    context = NewsContext("AAA", 10, headlines, "positive")

    result = analyze_ticker_news(make_analysis(signal="HOLD"), context)

    assert result.sentiment == "Bullish"
    assert not hasattr(result, "signal")


def test_write_ai_analysis_report(tmp_path: Path):
    output_path = tmp_path / "ai_analysis.md"
    analysis = AIAnalysis(
        ticker="AAA",
        technical_score=80,
        confidence=72,
        summary="Summary text.",
        sentiment="Neutral",
        risk_flags=[],
        opportunity_flags=["growth"],
    )

    write_ai_analysis_report({"AAA": analysis}, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "AI News Analysis" in content
    assert "AI Sentiment" in content
    assert "does not create BUY or SELL signals" in content
