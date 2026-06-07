from types import SimpleNamespace

from modules.risk import PortfolioRules, build_allocation_plan


def make_analysis(ticker: str, score: int, confidence: int = 80, volatility: float = 0.20):
    return SimpleNamespace(
        ticker=ticker,
        signal="BUY",
        score=score,
        confidence_score=confidence,
        volatility=volatility,
        entry_price=100.0,
        stop_loss=92.0,
        target_price=116.0,
        expected_holding_period="2-6 weeks",
    )


def test_allocation_respects_max_positions_and_minimum_score():
    rules = PortfolioRules(
        capital_nok=20000,
        max_positions=2,
        position_sizing="score_weighted",
        max_position_pct=0.50,
        cash_reserve_pct=0.05,
        stop_loss_pct=0.08,
        take_profit_pct=0.16,
        minimum_buy_score=70,
    )
    analyses = [
        make_analysis("AAA", 90),
        make_analysis("BBB", 80),
        make_analysis("CCC", 60),
    ]

    allocations = build_allocation_plan(analyses, rules)

    assert [allocation.ticker for allocation in allocations] == ["AAA", "BBB"]
    assert all(allocation.score >= 70 for allocation in allocations)


def test_allocation_calculates_risk_and_reward_amounts():
    rules = PortfolioRules(
        capital_nok=20000,
        max_positions=1,
        position_sizing="equal_weight",
        max_position_pct=0.25,
        cash_reserve_pct=0.05,
        stop_loss_pct=0.08,
        take_profit_pct=0.16,
        minimum_buy_score=70,
    )

    allocation = build_allocation_plan([make_analysis("AAA", 90)], rules)[0]

    assert allocation.suggested_amount_nok == 5000
    assert allocation.risk_amount_nok == 400
    assert allocation.reward_amount_nok == 800
