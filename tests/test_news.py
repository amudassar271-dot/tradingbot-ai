from modules.news import build_news_context, classify_news_sentiment, combined_confidence, NewsItem


def test_classify_positive_news_sentiment():
    sentiment = classify_news_sentiment("Company wins major contract after earnings beat")

    assert sentiment == "positive"


def test_classify_negative_news_sentiment():
    sentiment = classify_news_sentiment("Analyst downgrade follows profit warning")

    assert sentiment == "negative"


def test_classify_neutral_news_sentiment():
    sentiment = classify_news_sentiment("Company announces annual meeting date")

    assert sentiment == "neutral"


def test_build_news_context_scores_positive_headlines():
    headlines = [
        NewsItem("AAA", "Growth improves after contract win", "Publisher", "", "2026-01-01", "positive"),
        NewsItem("AAA", "Company announces annual meeting", "Publisher", "", "2026-01-01", "neutral"),
    ]

    context = build_news_context("AAA", headlines)

    assert context.news_score == 10


def test_build_news_context_scores_negative_headlines():
    headlines = [
        NewsItem("AAA", "Company faces investigation and lawsuit", "Publisher", "", "2026-01-01", "negative"),
    ]

    context = build_news_context("AAA", headlines)

    assert context.news_score == -10


def test_combined_confidence_is_bounded():
    assert combined_confidence(95, 10) == 100
    assert combined_confidence(5, -10) == 0
