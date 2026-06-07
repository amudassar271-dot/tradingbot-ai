from pathlib import Path

from modules.news import NewsContext, NewsItem
import modules.openai_analyst as openai_analyst
from modules.openai_analyst import (
    OpenAIMarketAnalysis,
    analyze_primary_strategy_with_openai,
    build_cache_key,
    build_market_analyst_prompt,
    candidate_confidence,
    estimate_api_cost,
    estimate_tokens,
    classify_openai_error,
    write_openai_analysis_report,
    write_openai_cache,
)
from modules.strategy_report import PrimaryStrategyReport, StrategyCandidate


def make_candidate():
    return StrategyCandidate(
        ticker="AAA",
        name="AAA Inc",
        market="US",
        rank=1,
        allocation_nok=15000,
        entry_price=100,
        stop_loss=85,
        momentum_score=72,
        momentum_30d=0.12,
        momentum_90d=0.20,
        relative_strength=0.05,
        reason="price is above SMA50.",
    )


def make_report():
    return PrimaryStrategyReport(
        strategy_name="momentum_portfolio",
        capital_nok=30000,
        top_n=2,
        rebalance_frequency="monthly",
        stop_loss_pct=0.15,
        momentum_threshold_pct=0.10,
        commission_nok=29,
        candidates=[make_candidate()],
        cash_reserve_nok=0,
        replacement_note="Keep AAA.",
    )


def test_candidate_confidence_uses_momentum_inputs():
    assert candidate_confidence(make_candidate()) == 100


def test_estimate_cost_is_positive():
    assert estimate_tokens("abcd" * 10) > 0
    assert estimate_api_cost(1000, 500) > 0


def test_prompt_contains_no_trade_instruction():
    news = NewsContext(
        "AAA",
        0,
        [NewsItem("AAA", "AAA signs new contract", "Publisher", "", "2026-01-01", "positive")],
        "positive",
    )

    prompt = build_market_analyst_prompt(make_candidate(), news)

    assert "must not create trades" in prompt
    assert "valid JSON" in prompt
    assert "AAA signs new contract" in prompt


def test_openai_analysis_uses_cache(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    candidate = make_candidate()
    prompt = build_market_analyst_prompt(candidate, None)
    cache_key = build_cache_key("test-model", prompt)
    cache_path = tmp_path / "openai_cache.json"
    write_openai_cache(
        {
            "responses": {
                cache_key: {
                    "market_summary": "Cached summary.",
                    "bull_case": ["growth"],
                    "bear_case": ["risk"],
                    "key_catalysts": ["earnings"],
                    "verdict": "Watchlist",
                    "estimated_output_tokens": 10,
                    "estimated_cost_usd": 0.001,
                }
            }
        },
        cache_path,
    )

    analyses = analyze_primary_strategy_with_openai(make_report(), {}, cache_path, model="test-model")

    assert analyses[0].cached
    assert analyses[0].market_summary == "Cached summary."


def test_openai_analysis_without_api_key_does_not_call_api(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    analyses = analyze_primary_strategy_with_openai(make_report(), {}, tmp_path / "cache.json", model="test-model")

    assert not analyses[0].api_used
    assert analyses[0].verdict == "Watchlist"
    assert analyses[0].openai_status == "No API key"
    assert "Local fallback" in analyses[0].market_summary


def test_openai_rate_limit_insufficient_quota_falls_back(tmp_path: Path, monkeypatch):
    class FakeRateLimitError(Exception):
        code = "insufficient_quota"

    def raise_quota(model, prompt):
        raise FakeRateLimitError("429 insufficient_quota")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(openai_analyst, "RateLimitError", FakeRateLimitError)
    monkeypatch.setattr(openai_analyst, "call_openai_market_analyst", raise_quota)

    analyses = analyze_primary_strategy_with_openai(make_report(), {}, tmp_path / "cache.json", model="test-model")

    assert analyses[0].openai_status == "Insufficient quota"
    assert not analyses[0].api_used
    assert analyses[0].verdict == "Watchlist"


def test_openai_authentication_failure_falls_back(tmp_path: Path, monkeypatch):
    class FakeAuthenticationError(Exception):
        pass

    def raise_auth(model, prompt):
        raise FakeAuthenticationError("bad key")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(openai_analyst, "AuthenticationError", FakeAuthenticationError)
    monkeypatch.setattr(openai_analyst, "call_openai_market_analyst", raise_auth)

    analyses = analyze_primary_strategy_with_openai(make_report(), {}, tmp_path / "cache.json", model="test-model")

    assert analyses[0].openai_status == "Authentication failed"


def test_openai_connection_failure_falls_back(tmp_path: Path, monkeypatch):
    class FakeAPIConnectionError(Exception):
        pass

    def raise_connection(model, prompt):
        raise FakeAPIConnectionError("network down")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(openai_analyst, "APIConnectionError", FakeAPIConnectionError)
    monkeypatch.setattr(openai_analyst, "call_openai_market_analyst", raise_connection)

    analyses = analyze_primary_strategy_with_openai(make_report(), {}, tmp_path / "cache.json", model="test-model")

    assert analyses[0].openai_status == "Connection failed"


def test_openai_status_error_429_is_insufficient_quota(monkeypatch):
    class FakeAPIStatusError(Exception):
        status_code = 429

    monkeypatch.setattr(openai_analyst, "APIStatusError", FakeAPIStatusError)

    assert classify_openai_error(FakeAPIStatusError("quota")) == "Insufficient quota"


def test_write_openai_analysis_report(tmp_path: Path):
    output_path = tmp_path / "openai_analysis.md"
    analysis = OpenAIMarketAnalysis(
        ticker="AAA",
        company_name="AAA Inc",
        momentum_score=72,
        confidence=90,
        market_summary="Summary.",
        bull_case=["growth"],
        bear_case=["valuation"],
        key_catalysts=["earnings"],
        verdict="Watchlist",
        estimated_input_tokens=100,
        estimated_output_tokens=50,
        estimated_cost_usd=0.0001,
        cached=False,
        api_used=True,
        openai_status="Success",
    )

    write_openai_analysis_report([analysis], output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "OpenAI Market Analysis" in content
    assert "does not create trades" in content
    assert "Cost Tracking" in content
    assert "OpenAI Status: Success" in content
    assert "AI Verdict" in content
