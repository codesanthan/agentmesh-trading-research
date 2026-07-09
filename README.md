# AgentMesh Trading Research

[![CI](https://github.com/codesanthan/agentmesh-trading-research/actions/workflows/ci.yml/badge.svg)](https://github.com/codesanthan/agentmesh-trading-research/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A ticker research report generator built on [AgentMesh](https://github.com/codesanthan/agentmesh).
Give it a ticker; it fetches real price history and recent news, runs the data
through an AgentMesh multi-agent pipeline (technical, sentiment, and risk
agents synthesized by a lead agent), and writes a structured research note.

**This produces research notes, not trading signals.** It does not place,
size, or recommend trades, and it never will -- that's a deliberate boundary,
not a missing feature. Nothing here is investment advice.

## Why this exists

It's a companion project to AgentMesh: a demonstration of the framework wired
to real, free data sources instead of the mock responses used in AgentMesh's
own examples. It's also a genuinely useful starting point for a research
assistant -- clone it, point it at a ticker, and you get a real report
grounded in real numbers.

## How it's free

- **Prices**: Yahoo Finance's public chart API (`query1.finance.yahoo.com`),
  called directly over `urllib` -- no API key, no SDK.
- **News**: Google News RSS, parsed with the standard library's
  `xml.etree` -- no API key, no SDK.
- **Synthesis**: deterministic by default. Each agent's output is built
  directly from the real fetched data (via AgentMesh's `MockProvider`), so
  the whole pipeline runs for $0 with no signup.

Want an LLM to actually *write* the final synthesis (reading the real
technical/sentiment/risk findings as context, the way AgentMesh's supervisor
strategy is designed to work)? Pass `--llm anthropic` or `--llm openai` and
set the matching API key as an environment variable. The first three agents
stay deterministic and free either way -- only the final synthesis step
optionally uses a real model.

## Quickstart

```bash
git clone https://github.com/codesanthan/agentmesh-trading-research.git
cd agentmesh-trading-research
pip install -e ".[dev]"

# Fully free, no API key
trading-research analyze AAPL

# Optional: real LLM synthesis (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-...
trading-research analyze AAPL --llm anthropic
```

Each run writes a Markdown report to `reports/<TICKER>_<date>.md` and prints
it to stdout.

## Architecture

```
src/trading_research/
  data/
    prices.py   Yahoo Finance chart API fetch + technical/volatility calc
    news.py     Google News RSS fetch + parse
  report.py     Wires real data into an AgentMesh Orchestrator + TaskGraph
  cli.py        `trading-research analyze <TICKER>`
```

The task graph is the same shape as AgentMesh's `research_team` example: a
`data_analyst` and `sentiment_analyst` run independently, a `risk_analyst`
depends on the technical output, and a `lead` agent (supervisor strategy)
synthesizes all three into one note.

CI runs the test suite against fixture data -- it does not call the live
Yahoo Finance / Google News endpoints, to keep the pipeline deterministic and
avoid rate-limiting from CI runners.

## License

MIT -- see [LICENSE](LICENSE).
