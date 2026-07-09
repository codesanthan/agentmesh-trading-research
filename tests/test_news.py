"""Tests for trading_research.data.news -- uses fixture RSS XML, no live network calls."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from trading_research.data.news import NewsFetchError, fetch_news_snapshot

FIXTURE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Google News</title>
    <item>
      <title>Company beats earnings expectations, shares surge</title>
      <source>Reuters</source>
      <pubDate>Thu, 09 Jul 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Regulators open probe into company practices</title>
      <source>Bloomberg</source>
      <pubDate>Wed, 08 Jul 2026 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Company announces new product line</title>
      <source>TechCrunch</source>
      <pubDate>Tue, 07 Jul 2026 15:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class _FakeResponse:
    def __init__(self, body: str):
        self._body = body.encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_fetch_news_snapshot_scores_headlines():
    with patch("urllib.request.urlopen", return_value=_FakeResponse(FIXTURE_RSS)):
        snapshot = fetch_news_snapshot("Example Co stock")

    assert len(snapshot.headlines) == 3
    assert snapshot.positive_hits >= 1
    assert snapshot.negative_hits >= 1
    assert "Reuters" in snapshot.sentiment_summary()


def test_fetch_news_snapshot_raises_on_bad_xml():
    with patch("urllib.request.urlopen", return_value=_FakeResponse("not xml")):
        with pytest.raises(NewsFetchError):
            fetch_news_snapshot("Example Co stock")


def test_fetch_news_snapshot_raises_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        with pytest.raises(NewsFetchError):
            fetch_news_snapshot("Example Co stock")
