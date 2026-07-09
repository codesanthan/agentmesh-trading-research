"""Wire real price and news data into an AgentMesh multi-agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from agentmesh.config import load_workflow
from agentmesh.core.state import ExecutionState
from agentmesh.providers.base import Provider

from trading_research.data.news import NewsFetchError, fetch_news_snapshot
from trading_research.data.prices import PriceFetchError, fetch_price_snapshot


class ReportError(Exception):
    pass


@dataclass
class ResearchInputs:
    ticker: str
    technical_summary: str
    sentiment_summary: str
    risk_summary: str


def gather_inputs(ticker: str) -> ResearchInputs:
    """Fetch real price and news data and turn it into agent-ready text."""
    try:
        prices = fetch_price_snapshot(ticker)
    except PriceFetchError as exc:
        raise ReportError(str(exc)) from exc

    try:
        news = fetch_news_snapshot(f"{ticker} stock")
    except NewsFetchError as exc:
        raise ReportError(str(exc)) from exc

    return ResearchInputs(
        ticker=prices.ticker,
        technical_summary=prices.technical_summary(),
        sentiment_summary=news.sentiment_summary(),
        risk_summary=prices.risk_summary(),
    )


def _default_synthesis(inputs: ResearchInputs) -> str:
    return (
        f"## Research Summary: {inputs.ticker}\n\n"
        f"**Technical**: {inputs.technical_summary}\n\n"
        f"**Sentiment**: {inputs.sentiment_summary}\n\n"
        f"**Risk**: {inputs.risk_summary}\n\n"
        "**Open questions**: this note is built entirely from technical price "
        "data and headline-level news scanning -- it does not incorporate "
        "fundamentals (earnings, valuation multiples), management commentary, "
        "or portfolio-level context. Treat it as a starting point for further "
        "research, not a conclusion.\n\n"
        "_No buy/sell/hold recommendation is made here by design._"
    )


def build_workflow_spec(inputs: ResearchInputs, lead_provider: Provider | None = None) -> dict:
    """Build an AgentMesh workflow spec dict grounded in real fetched data.

    Three agents get a `MockProvider` whose response is the real data summary
    computed above -- their output is deterministic and free. The fourth
    agent (`lead`) either gets the same treatment (a Python-built synthesis
    template, still free) or a real `Provider` passed in via `lead_provider`,
    in which case AgentMesh's supervisor-synthesis mechanism feeds it the
    real outputs of the other three agents as context.
    """
    spec: dict = {
        "strategy": "supervisor",
        "supervisor": "lead",
        "agents": [
            {
                "name": "data_analyst",
                "system_prompt": (
                    "You summarize price action and technical indicators for a "
                    "given ticker, factually and without giving buy/sell advice."
                ),
                "provider": {"type": "mock", "default": inputs.technical_summary},
            },
            {
                "name": "sentiment_analyst",
                "system_prompt": (
                    "You synthesize recent news coverage and public sentiment for "
                    "a given ticker, noting both positive and negative signals."
                ),
                "provider": {"type": "mock", "default": inputs.sentiment_summary},
            },
            {
                "name": "risk_analyst",
                "system_prompt": (
                    "You assess risk factors -- volatility, drawdown, volume -- "
                    "relevant to a potential position, without giving buy/sell advice."
                ),
                "provider": {"type": "mock", "default": inputs.risk_summary},
            },
            {
                "name": "lead",
                "system_prompt": (
                    "You are a research lead. Synthesize your team's findings into "
                    "one structured research note: summarize the data, sentiment, "
                    "and risk findings, then note open questions. Do not issue a "
                    "buy/sell/hold recommendation -- present the evidence for the "
                    "reader to decide."
                ),
            },
        ],
        "tasks": [
            {
                "id": "market_data",
                "agent": "data_analyst",
                "prompt": f"Summarize the recent technical indicators for {inputs.ticker}.",
            },
            {
                "id": "sentiment",
                "agent": "sentiment_analyst",
                "prompt": f"Summarize the recent news and sentiment for {inputs.ticker}.",
            },
            {
                "id": "risk",
                "agent": "risk_analyst",
                "depends_on": ["market_data"],
                "prompt": f"Assess the risk factors for {inputs.ticker}, given the technical picture.",
            },
        ],
    }

    if lead_provider is None:
        spec["agents"][3]["provider"] = {"type": "mock", "default": _default_synthesis(inputs)}

    return spec


def run_report(
    ticker: str, lead_provider: Provider | None = None
) -> tuple[ResearchInputs, ExecutionState]:
    """Fetch real data for `ticker` and run it through the AgentMesh pipeline."""
    inputs = gather_inputs(ticker)
    spec = build_workflow_spec(inputs, lead_provider=lead_provider)

    orchestrator, graph = load_workflow(spec)

    if lead_provider is not None:
        orchestrator.agents["lead"].provider = lead_provider

    state = orchestrator.run(graph)
    return inputs, state


def render_markdown(ticker: str, state: ExecutionState) -> str:
    """Render the orchestrator's final synthesis (or raw results) as Markdown."""
    synthesis = state.results.get("__supervisor_synthesis__")
    if synthesis is not None and synthesis.output:
        return synthesis.output

    # Fallback: if synthesis failed for some reason, show whatever succeeded.
    lines = [f"# Research note: {ticker}", ""]
    for task_id, result in state.results.items():
        lines.append(f"## {task_id} ({result.agent})")
        lines.append(result.output or result.error or "")
        lines.append("")
    return "\n".join(lines)
