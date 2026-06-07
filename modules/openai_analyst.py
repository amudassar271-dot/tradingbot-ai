from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os

from modules.news import NewsContext
from modules.strategy_report import PrimaryStrategyReport, StrategyCandidate

try:
    from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError
except ModuleNotFoundError:
    class RateLimitError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class APIStatusError(Exception):
        pass


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_CACHE_PATH = Path("data/openai_analysis_cache.json")
INPUT_COST_PER_1M_TOKENS = 0.15
OUTPUT_COST_PER_1M_TOKENS = 0.60


@dataclass(frozen=True)
class OpenAIMarketAnalysis:
    ticker: str
    company_name: str
    momentum_score: float
    confidence: int
    market_summary: str
    bull_case: list[str]
    bear_case: list[str]
    key_catalysts: list[str]
    verdict: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    cached: bool
    api_used: bool
    openai_status: str


def analyze_primary_strategy_with_openai(
    strategy_report: PrimaryStrategyReport,
    news_contexts: dict[str, NewsContext],
    cache_path: Path = DEFAULT_CACHE_PATH,
    model: str | None = None,
) -> list[OpenAIMarketAnalysis]:
    cache_exists = cache_path.exists()
    cache = load_openai_cache(cache_path)
    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    analyses = []
    cache_changed = not cache_exists

    for candidate in strategy_report.candidates:
        news_context = news_contexts.get(candidate.ticker)
        prompt = build_market_analyst_prompt(candidate, news_context)
        cache_key = build_cache_key(selected_model, prompt)
        cached_payload = cache.get("responses", {}).get(cache_key)
        input_tokens = estimate_tokens(prompt)

        if cached_payload:
            analyses.append(analysis_from_payload(candidate, cached_payload, input_tokens, cached=True, api_used=True))
            continue

        if not os.getenv("OPENAI_API_KEY"):
            payload = build_local_fallback_payload(candidate, news_context, "No API key")
            analyses.append(analysis_from_payload(candidate, payload, input_tokens, cached=False, api_used=False))
            continue

        try:
            payload, output_text = call_openai_market_analyst(selected_model, prompt)
            output_tokens = estimate_tokens(output_text)
            payload["estimated_output_tokens"] = output_tokens
            payload["estimated_cost_usd"] = estimate_api_cost(input_tokens, output_tokens)
            payload["openai_status"] = "Success"
            cache.setdefault("responses", {})[cache_key] = payload
            cache_changed = True
            analyses.append(analysis_from_payload(candidate, payload, input_tokens, cached=False, api_used=True))
        except (RateLimitError, AuthenticationError, APIConnectionError, APIStatusError) as exc:
            status = classify_openai_error(exc)
            payload = build_local_fallback_payload(candidate, news_context, status)
            analyses.append(analysis_from_payload(candidate, payload, input_tokens, cached=False, api_used=False))

    if cache_changed:
        write_openai_cache(cache, cache_path)
    return analyses


def build_market_analyst_prompt(candidate: StrategyCandidate, news_context: NewsContext | None) -> str:
    headlines = news_context.headlines if news_context else []
    headline_lines = "\n".join(
        f"- {headline.published_date} | {headline.publisher}: {headline.title}"
        for headline in headlines
    ) or "- No recent yfinance headlines found."
    technical_summary = (
        f"Ticker: {candidate.ticker}\n"
        f"Company: {candidate.name}\n"
        f"Momentum score: {candidate.momentum_score:.2f}\n"
        f"Confidence: {candidate_confidence(candidate)}\n"
        f"30D momentum: {candidate.momentum_30d:.2%}\n"
        f"90D momentum: {format_optional_pct(candidate.momentum_90d)}\n"
        f"Relative strength versus QQQ/SPY: {format_optional_pct(candidate.relative_strength)}\n"
        f"Technical summary: {candidate.reason}"
    )
    return (
        "You are a market analyst for a research-only portfolio tool.\n"
        "You must not create trades, change allocation, or create BUY/SELL signals.\n"
        "Analyze and explain only.\n\n"
        f"{technical_summary}\n\n"
        "Recent news headlines:\n"
        f"{headline_lines}\n\n"
        "Return valid JSON with exactly these keys:\n"
        "market_summary: string with 2-5 sentences,\n"
        "bull_case: array of concise reasons to own,\n"
        "bear_case: array of concise risks,\n"
        "key_catalysts: array covering relevant earnings, contracts, macro events, regulation, AI trends, or sector trends,\n"
        "verdict: one of Strong Candidate, Watchlist, Avoid.\n"
    )


def call_openai_market_analyst(model: str, prompt: str) -> tuple[dict, str]:
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You produce concise JSON market analysis for research only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    output_text = response.choices[0].message.content or "{}"
    payload = normalize_openai_payload(json.loads(output_text))
    return payload, output_text


def normalize_openai_payload(payload: dict) -> dict:
    verdict = str(payload.get("verdict", "Watchlist")).strip()
    if verdict not in {"Strong Candidate", "Watchlist", "Avoid"}:
        verdict = "Watchlist"
    return {
        "market_summary": str(payload.get("market_summary", "")).strip() or "No summary returned.",
        "bull_case": normalize_string_list(payload.get("bull_case", [])),
        "bear_case": normalize_string_list(payload.get("bear_case", [])),
        "key_catalysts": normalize_string_list(payload.get("key_catalysts", [])),
        "verdict": verdict,
    }


def normalize_string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return ["No specific items returned."]


def build_local_fallback_payload(
    candidate: StrategyCandidate,
    news_context: NewsContext | None,
    openai_status: str,
) -> dict:
    headlines = news_context.headlines if news_context else []
    headline_summary = (
        f"Recent local news context includes {len(headlines)} headline(s)."
        if headlines
        else "No recent yfinance headlines were available for local fallback analysis."
    )
    news_tone = news_context.explanation if news_context else "No local news explanation available."
    return {
        "market_summary": (
            f"OpenAI Status: {openai_status}. Local fallback used technical momentum and yfinance news context. "
            f"{candidate.ticker} has a momentum score of {candidate.momentum_score:.2f}, "
            f"30-day momentum of {candidate.momentum_30d:.2%}, and relative strength of {format_optional_pct(candidate.relative_strength)}. "
            f"{headline_summary} {news_tone}"
        ),
        "bull_case": build_local_bull_case(candidate, headlines),
        "bear_case": build_local_bear_case(candidate, openai_status),
        "key_catalysts": build_local_catalysts(headlines),
        "verdict": "Watchlist",
        "estimated_output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "openai_status": openai_status,
    }


def build_local_bull_case(candidate: StrategyCandidate, headlines) -> list[str]:
    items = [
        f"Momentum score is {candidate.momentum_score:.2f}.",
        f"30-day momentum is {candidate.momentum_30d:.2%}.",
    ]
    if candidate.momentum_90d is not None:
        items.append(f"90-day momentum is {candidate.momentum_90d:.2%}.")
    if candidate.relative_strength is not None and candidate.relative_strength > 0:
        items.append("Relative strength is positive versus QQQ/SPY.")
    if headlines:
        items.append("Recent yfinance headlines are available for manual review.")
    return items


def build_local_bear_case(candidate: StrategyCandidate, openai_status: str) -> list[str]:
    items = [
        f"OpenAI qualitative analysis unavailable: {openai_status}.",
        "Momentum can reverse quickly after market, earnings, or macro news.",
    ]
    if candidate.relative_strength is not None and candidate.relative_strength < 0:
        items.append("Relative strength is negative versus QQQ/SPY.")
    return items


def build_local_catalysts(headlines) -> list[str]:
    catalysts = [
        "Earnings and company guidance.",
        "Macro events and sector rotation.",
        "Regulation and commodity/sector trends where relevant.",
        "AI trends where relevant to the company or sector.",
    ]
    if headlines:
        catalysts.append("Recent yfinance headlines listed in the news report.")
    return catalysts


def analysis_from_payload(
    candidate: StrategyCandidate,
    payload: dict,
    input_tokens: int,
    cached: bool,
    api_used: bool,
) -> OpenAIMarketAnalysis:
    output_tokens = int(payload.get("estimated_output_tokens", estimate_tokens(json.dumps(payload))))
    return OpenAIMarketAnalysis(
        ticker=candidate.ticker,
        company_name=candidate.name,
        momentum_score=candidate.momentum_score,
        confidence=candidate_confidence(candidate),
        market_summary=str(payload.get("market_summary", "")),
        bull_case=normalize_string_list(payload.get("bull_case", [])),
        bear_case=normalize_string_list(payload.get("bear_case", [])),
        key_catalysts=normalize_string_list(payload.get("key_catalysts", [])),
        verdict=str(payload.get("verdict", "Watchlist")),
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        estimated_cost_usd=float(payload.get("estimated_cost_usd", estimate_api_cost(input_tokens, output_tokens))),
        cached=cached,
        api_used=api_used,
        openai_status=str(payload.get("openai_status", "Success" if api_used else "No API key")),
    )


def classify_openai_error(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return "Authentication failed"
    if isinstance(exc, APIConnectionError):
        return "Connection failed"
    if isinstance(exc, RateLimitError):
        text = str(exc).lower()
        code = str(getattr(exc, "code", "")).lower()
        if "insufficient_quota" in text or "insufficient_quota" in code or "quota" in text:
            return "Insufficient quota"
        return "Connection failed"
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        text = str(exc).lower()
        if status_code == 401:
            return "Authentication failed"
        if status_code == 429 or "insufficient_quota" in text or "quota" in text:
            return "Insufficient quota"
        return "Connection failed"
    return "Connection failed"


def candidate_confidence(candidate: StrategyCandidate) -> int:
    score = 50
    if candidate.momentum_30d > 0.10:
        score += 20
    if candidate.momentum_90d is not None and candidate.momentum_90d > 0.10:
        score += 15
    if candidate.relative_strength is not None and candidate.relative_strength > 0:
        score += 10
    if candidate.momentum_score > 50:
        score += 5
    return max(0, min(100, score))


def build_cache_key(model: str, prompt: str) -> str:
    return sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def estimate_api_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * INPUT_COST_PER_1M_TOKENS
        + output_tokens / 1_000_000 * OUTPUT_COST_PER_1M_TOKENS
    )


def load_openai_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {"updated_at": "", "responses": {}}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"updated_at": "", "responses": {}}


def write_openai_cache(cache: dict, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def write_openai_analysis_report(analyses: list[OpenAIMarketAnalysis], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_input_tokens = sum(analysis.estimated_input_tokens for analysis in analyses)
    total_output_tokens = sum(analysis.estimated_output_tokens for analysis in analyses)
    total_cost = sum(analysis.estimated_cost_usd for analysis in analyses)
    lines = [
        "# OpenAI Market Analysis",
        "",
        "This layer explains and analyzes only. It does not create trades, change allocation, or create BUY/SELL signals.",
        "",
        "## Cost Tracking",
        "",
        f"- Estimated input tokens: {total_input_tokens:,}",
        f"- Estimated output tokens: {total_output_tokens:,}",
        f"- Estimated API cost: ${total_cost:.6f}",
        "",
    ]

    if not analyses:
        lines.append("No selected momentum candidates were available for OpenAI analysis.")
    for analysis in analyses:
        lines.extend([
            f"## {analysis.ticker} - {analysis.company_name}",
            "",
            f"- Momentum score: {analysis.momentum_score:.2f}",
            f"- Confidence: {analysis.confidence}",
            f"- OpenAI Status: {analysis.openai_status}",
            f"- AI Verdict: {analysis.verdict}",
            f"- Source: {'cache' if analysis.cached else ('OpenAI API' if analysis.api_used else 'local fallback')}",
            f"- Estimated tokens: {analysis.estimated_input_tokens + analysis.estimated_output_tokens:,}",
            f"- Estimated cost: ${analysis.estimated_cost_usd:.6f}",
            "",
            "### Market Summary",
            "",
            analysis.market_summary,
            "",
            "### Bull Case",
            "",
            *[f"- {item}" for item in analysis.bull_case],
            "",
            "### Bear Case",
            "",
            *[f"- {item}" for item in analysis.bear_case],
            "",
            "### Key Catalysts",
            "",
            *[f"- {item}" for item in analysis.key_catalysts],
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def format_optional_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"
