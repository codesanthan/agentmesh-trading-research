"""Tests for trading_research.report -- exercises the full pipeline with fixture data."""

from __future__ import annotations

from unittest.mock import patch

from trading_research.data.news import Headline, NewsSnapshot
from trading_research.data.prices import PriceSnapshot
from trading_research.report import ResearchInputs, gather_inputs, render_markdown, run_report


def _fake_price_snapshot() -> PriceSnapshot:
    return PriceSnapshot(
        ticker="TEST",
        last_close=150.0,
        period_change_pct=5.0,
        sma_50=140.0,
        above_sma_50=True,
        fifty_two_week_high=180.0,
        fifty_two_week_low=110.0,
        annualized_volatility_pct=30.0,
        recent_avg_volume=1_500_000,
        prior_avg_volume=1_200_000,
        volume_trend="rising",
    )


def _fake_news_snapshot() -> NewsSnapshot:
    snapshot = NewsSnapshot(query="TEST stock")
    snapshot.headlines.append(Headline(title="Test headline", source="Reuters", published=""))
    snapshot.positive_hits = 1
    snapshot.negative_hits = 0
    return snapshot


def test_gather_inputs_builds_summaries_from_real_data_shape():
    with (
        patch("trading_research.report.fetch_price_snapshot", return_value=_fake_price_snapshot()),
        patch("trading_research.report.fetch_news_snapshot", return_value=_fake_news_snapshot()),
    ):
        inputs = gather_inputs("TEST")

    assert isinstance(inputs, ResearchInputs)
    assert inputs.ticker == "TEST"
    assert "TEST" in inputs.technical_summary
    assert "volatility" in inputs.risk_summary.lower()


def test_run_report_produces_a_synthesized_note_without_any_llm():
    with (
        patch("trading_research.report.fetch_price_snapshot", return_value=_fake_price_snapshot()),
        patch("trading_research.report.fetch_news_snapshot", return_value=_fake_news_snapshot()),
    ):
        inputs, state = run_report("TEST", lead_provider=None)

    assert state.results["market_data"].output == inputs.technical_summary
    assert state.results["sentiment"].output == inputs.sentiment_summary
    assert state.results["risk"].output == inputs.risk_summary

    report = render_markdown(inputs.ticker, state)
    assert "TEST" in report
    assert "No buy/sell/hold recommendation" in report
