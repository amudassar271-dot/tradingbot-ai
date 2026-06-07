from dataclasses import dataclass
from pathlib import Path

from modules.news import NewsContext
from modules.strategy import StockAnalysis


RISK_FLAGS = [
    "lawsuit",
    "guidance cut",
    "weak demand",
    "sanctions",
    "regulation",
    "supply chain",
]

OPPORTUNITY_FLAGS = [
    "contract",
    "growth",
    "dividend",
    "upgrade",
    "earnings beat",
    "ai adoption",
]


@dataclass(frozen=True)
class AIAnalysis:
    ticker: str
    technical_score: int
    confidence: int
    summary: str
    sentiment: str
    risk_flags: list[str]
    opportunity_flags: list[str]


def analyze_ticker_news(
    analysis: StockAnalysis,
    news_context: NewsContext | None,
) -> AIAnalysis:
    headlines = news_context.headlines if news_context else []
    headline_text = " ".join(headline.title for headline in headlines).lower()
    risk_flags = find_flags(headline_text, RISK_FLAGS)
    opportunity_flags = find_flags(headline_text, OPPORTUNITY_FLAGS)
    sentiment = classify_ai_sentiment(analysis, risk_flags, opportunity_flags, news_context)
    summary = build_ai_summary(analysis, headlines, sentiment, risk_flags, opportunity_flags)

    return AIAnalysis(
        ticker=analysis.ticker,
        technical_score=analysis.score,
        confidence=analysis.confidence_score,
        summary=summary,
        sentiment=sentiment,
        risk_flags=risk_flags,
        opportunity_flags=opportunity_flags,
    )


def analyze_watchlist_news(
    analyses: list[StockAnalysis],
    news_contexts: dict[str, NewsContext],
) -> dict[str, AIAnalysis]:
    return {
        analysis.ticker: analyze_ticker_news(analysis, news_contexts.get(analysis.ticker))
        for analysis in sorted(analyses, key=lambda item: item.ticker)
    }


def classify_ai_sentiment(
    analysis: StockAnalysis,
    risk_flags: list[str],
    opportunity_flags: list[str],
    news_context: NewsContext | None,
) -> str:
    news_score = news_context.news_score if news_context else 0
    sentiment_score = news_score + len(opportunity_flags) * 3 - len(risk_flags) * 4

    if analysis.score >= 75:
        sentiment_score += 2
    elif analysis.score < 50:
        sentiment_score -= 2

    if sentiment_score >= 6:
        return "Bullish"
    if sentiment_score <= -6:
        return "Bearish"
    return "Neutral"


def find_flags(text: str, flags: list[str]) -> list[str]:
    return [flag for flag in flags if flag in text]


def build_ai_summary(
    analysis: StockAnalysis,
    headlines,
    sentiment: str,
    risk_flags: list[str],
    opportunity_flags: list[str],
) -> str:
    if headlines:
        headline_sentence = f"Latest headlines for {analysis.ticker} provide {len(headlines)} news item(s) for review."
    else:
        headline_sentence = f"No recent yfinance headlines were found for {analysis.ticker}."

    technical_sentence = (
        f"The technical score is {analysis.score} with confidence {analysis.confidence_score}, "
        f"while the current technical signal remains {analysis.signal}."
    )
    context_sentence = f"AI sentiment is {sentiment} based on the available headlines and technical backdrop."

    flag_parts = []
    if risk_flags:
        flag_parts.append("risk flags: " + ", ".join(risk_flags))
    if opportunity_flags:
        flag_parts.append("opportunity flags: " + ", ".join(opportunity_flags))
    flags_sentence = "Detected " + "; ".join(flag_parts) + "." if flag_parts else "No configured risk or opportunity flags were detected."

    return " ".join([headline_sentence, technical_sentence, context_sentence, flags_sentence])


def write_ai_analysis_report(
    ai_analyses: dict[str, AIAnalysis],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI News Analysis",
        "",
        "AI analysis is context only. It does not create BUY or SELL signals and does not affect allocation.",
        "",
    ]

    for ticker, analysis in sorted(ai_analyses.items()):
        lines.extend([
            f"## {ticker}",
            "",
            f"- Technical score: {analysis.technical_score}",
            f"- Confidence: {analysis.confidence}",
            f"- AI Sentiment: {analysis.sentiment}",
            "- AI Risk Flags: " + format_flags(analysis.risk_flags),
            "- AI Opportunity Flags: " + format_flags(analysis.opportunity_flags),
            "",
            "### AI Summary",
            "",
            analysis.summary,
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def format_flags(flags: list[str]) -> str:
    if not flags:
        return "none"
    return ", ".join(flags)
