"""Command-line entry point: `trading-research analyze <TICKER>`."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from agentmesh.providers.base import Provider

from trading_research.report import ReportError, render_markdown, run_report

REPORTS_DIR = Path("reports")


def _build_lead_provider(llm: str | None) -> Provider | None:
    if llm is None:
        return None
    if llm == "anthropic":
        from agentmesh.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model="claude-sonnet-4-5")
    if llm == "openai":
        from agentmesh.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(model="gpt-4o-mini")
    raise ValueError(f"Unknown --llm value '{llm}'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trading-research", description="Generate a real-data ticker research note."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a ticker")
    analyze_parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL")
    analyze_parser.add_argument(
        "--llm",
        choices=["anthropic", "openai"],
        default=None,
        help="Use a real LLM for the final synthesis step (requires the matching API key)",
    )
    analyze_parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print the report but don't write it to reports/",
    )

    args = parser.parse_args(argv)

    if args.command == "analyze":
        try:
            lead_provider = _build_lead_provider(args.llm)
            inputs, state = run_report(args.ticker, lead_provider=lead_provider)
        except ReportError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        report = render_markdown(inputs.ticker, state)
        print(report)

        if not args.no_save:
            REPORTS_DIR.mkdir(exist_ok=True)
            out_path = REPORTS_DIR / f"{inputs.ticker}_{date.today().isoformat()}.md"
            out_path.write_text(report)
            print(f"\nSaved to {out_path}", file=sys.stderr)

        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
