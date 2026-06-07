from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
import json

from modules.strategy import clamp


POSITIVE_KEYWORDS = [
    "contract",
    "growth",
    "upgrade",
    "profit",
    "earnings beat",
    "buyback",
    "dividend increase",
    "guidance raised",
    "strong demand",
]

NEGATIVE_KEYWORDS = [
    "lawsuit",
    "downgrade",
    "loss",
    "warning",
    "profit warning",
    "weak demand",
    "investigation",
    "sanctions",
    "bankruptcy",
    "guidance cut",
]


class WatchlistLike(Protocol):
    ticker: str
    name: str
    market: str


class NewsConfigLike(Protocol):
    enabled: bool
    max_headlines_per_ticker: int
    sentiment_enabled: bool
    cache_path: Path
    output_path: Path


@dataclass(frozen=True)
class NewsItem:
    ticker: str
    title: str
    publisher: str
    link: str
    published_date: str
    sentiment: str


@dataclass(frozen=True)
class NewsContext:
    ticker: str
    news_score: int
    headlines: list[NewsItem]
    explanation: str


def fetch_news_for_watchlist(
    watchlist: list[WatchlistLike],
    config: NewsConfigLike,
) -> dict[str, NewsContext]:
    if not config.enabled:
        return {
            item.ticker: NewsContext(item.ticker, 0, [], "News disabled in config.")
            for item in watchlist
        }

    contexts = {}
    for item in watchlist:
        headlines = fetch_ticker_news(item.ticker, config.max_headlines_per_ticker)
        if config.sentiment_enabled:
            headlines = [
                NewsItem(
                    ticker=headline.ticker,
                    title=headline.title,
                    publisher=headline.publisher,
                    link=headline.link,
                    published_date=headline.published_date,
                    sentiment=classify_news_sentiment(headline.title),
                )
                for headline in headlines
            ]
        contexts[item.ticker] = build_news_context(item.ticker, headlines)

    write_news_cache(contexts, config.cache_path)
    return contexts


def fetch_ticker_news(ticker: str, limit: int) -> list[NewsItem]:
    try:
        import yfinance as yf

        raw_news = yf.Ticker(ticker).news or []
    except Exception:
        raw_news = []

    headlines = []
    for raw_item in raw_news[:limit]:
        normalized = normalize_news_item(ticker, raw_item)
        if normalized.title:
            headlines.append(normalized)
    return headlines


def normalize_news_item(ticker: str, raw_item: dict) -> NewsItem:
    content = raw_item.get("content", {}) if isinstance(raw_item, dict) else {}
    provider = content.get("provider", {})
    canonical_url = content.get("canonicalUrl", {})
    click_url = content.get("clickThroughUrl", {})
    title = str(raw_item.get("title") or content.get("title") or "").strip()
    publisher = str(
        raw_item.get("publisher")
        or get_nested_value(provider, "displayName")
        or get_nested_value(provider, "name")
        or (provider if isinstance(provider, str) else "")
        or "Unknown"
    ).strip()
    link = str(
        raw_item.get("link")
        or get_nested_value(canonical_url, "url")
        or get_nested_value(click_url, "url")
        or (canonical_url if isinstance(canonical_url, str) else "")
        or (click_url if isinstance(click_url, str) else "")
        or ""
    ).strip()
    published_raw = raw_item.get("providerPublishTime") or content.get("pubDate") or content.get("displayTime")
    published_date = format_published_date(published_raw)

    return NewsItem(
        ticker=ticker,
        title=title,
        publisher=publisher,
        link=link,
        published_date=published_date,
        sentiment=classify_news_sentiment(title),
    )


def get_nested_value(value, key: str):
    if isinstance(value, dict):
        return value.get(key)
    return None


def format_published_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d")
    text = str(value)
    if "T" in text:
        return text.split("T", 1)[0]
    return text[:10]


def classify_news_sentiment(title: str) -> str:
    lower_title = title.lower()
    positive_hits = count_keyword_hits(lower_title, POSITIVE_KEYWORDS)
    negative_hits = count_keyword_hits(lower_title, NEGATIVE_KEYWORDS)

    if positive_hits > negative_hits and positive_hits > 0:
        return "positive"
    if negative_hits > positive_hits and negative_hits > 0:
        return "negative"
    return "neutral"


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def build_news_context(ticker: str, headlines: list[NewsItem]) -> NewsContext:
    if not headlines:
        return NewsContext(ticker, 0, [], "No recent ticker news found from yfinance.")

    positive_count = sum(1 for headline in headlines if headline.sentiment == "positive")
    negative_count = sum(1 for headline in headlines if headline.sentiment == "negative")

    if positive_count > negative_count:
        return NewsContext(ticker, 10, headlines, "Recent headlines lean positive.")
    if negative_count > positive_count:
        return NewsContext(ticker, -10, headlines, "Recent headlines lean negative.")
    return NewsContext(ticker, 0, headlines, "Recent headlines are neutral or mixed.")


def combined_confidence(technical_confidence: int, news_score: int) -> int:
    return int(round(clamp(technical_confidence + news_score, 0, 100)))


def write_news_cache(contexts: dict[str, NewsContext], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "tickers": {
            ticker: {
                "news_score": context.news_score,
                "explanation": context.explanation,
                "headlines": [asdict(headline) for headline in context.headlines],
            }
            for ticker, context in sorted(contexts.items())
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_news_report(contexts: dict[str, NewsContext], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# News Report",
        "",
        "News is used for context and confidence adjustment only. It does not create BUY signals.",
        "",
    ]

    for ticker, context in sorted(contexts.items()):
        lines.extend([
            f"## {ticker}",
            "",
            f"- News score: {context.news_score}",
            f"- Explanation: {context.explanation}",
            "",
        ])
        if context.headlines:
            lines.extend([
                "| Published | Publisher | Sentiment | Title | Link |",
                "| --- | --- | --- | --- | --- |",
            ])
            for headline in context.headlines:
                link = f"[link]({headline.link})" if headline.link else ""
                lines.append(
                    f"| {headline.published_date} | {headline.publisher} | "
                    f"{headline.sentiment} | {headline.title} | {link} |"
                )
        else:
            lines.append("No news found.")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
