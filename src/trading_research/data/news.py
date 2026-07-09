"""Fetch and lightly score recent headlines from Google News RSS.

No API key required -- Google News publishes a public RSS feed for any
search query. Sentiment scoring here is a simple, transparent keyword
heuristic (not an LLM call), so it stays free and deterministic.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

RSS_URL = "https://news.google.com/rss/search"
USER_AGENT = "Mozilla/5.0 (compatible; agentmesh-trading-research/0.1)"

POSITIVE_WORDS = {
    "surge", "surges", "soar", "soars", "beat", "beats", "record", "rally",
    "rallies", "upgrade", "upgrades", "gain", "gains", "strong", "growth",
    "outperform", "bullish", "jump", "jumps", "rise", "rises", "higher",
    "profit", "profits", "win", "wins",
}
NEGATIVE_WORDS = {
    "plunge", "plunges", "drop", "drops", "fall", "falls", "miss", "misses",
    "downgrade", "downgrades", "loss", "losses", "weak", "decline",
    "declines", "bearish", "slump", "cuts", "lawsuit", "probe", "recall",
    "lower", "sinks", "sink", "warns", "warning", "layoffs", "investigation",
}


class NewsFetchError(Exception):
    pass


@dataclass
class Headline:
    title: str
    source: str
    published: str


@dataclass
class NewsSnapshot:
    query: str
    headlines: list[Headline] = field(default_factory=list)
    positive_hits: int = 0
    negative_hits: int = 0

    @property
    def tone(self) -> str:
        if self.positive_hits == self.negative_hits:
            return "neutral"
        return "positive-leaning" if self.positive_hits > self.negative_hits else "negative-leaning"

    def sentiment_summary(self) -> str:
        if not self.headlines:
            return f"No recent news coverage found for {self.query}."
        lines = [
            f"Scanned {len(self.headlines)} recent headlines for {self.query}: "
            f"{self.positive_hits} with positive-coded language, "
            f"{self.negative_hits} with negative-coded language -- "
            f"overall tone reads {self.tone}.",
            "Recent headlines:",
        ]
        for h in self.headlines[:5]:
            lines.append(f"  - \"{h.title}\" ({h.source})")
        lines.append(
            "This is a keyword-based heuristic over headlines only, not a "
            "full-text or analyst sentiment read -- treat it as a rough signal."
        )
        return "\n".join(lines)


def _score(text: str) -> tuple[int, int]:
    words = {w.strip(".,!?:;\"'()").lower() for w in text.split()}
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    return pos, neg


def fetch_news_snapshot(query: str, max_items: int = 8) -> NewsSnapshot:
    """Fetch recent headlines for `query` from Google News RSS and score their tone."""
    params = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    url = f"{RSS_URL}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
    except Exception as exc:  # noqa: BLE001 - surfaced as a typed error for the CLI
        raise NewsFetchError(f"Could not fetch news for '{query}': {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise NewsFetchError(f"Could not parse news feed for '{query}': {exc}") from exc

    snapshot = NewsSnapshot(query=query)
    items = root.findall("./channel/item")[:max_items]
    for item in items:
        title = (item.findtext("title") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        published = (item.findtext("pubDate") or "").strip()
        if not title:
            continue
        snapshot.headlines.append(Headline(title=title, source=source, published=published))
        pos, neg = _score(title)
        snapshot.positive_hits += pos
        snapshot.negative_hits += neg

    return snapshot
