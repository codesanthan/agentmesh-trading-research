"""Tests for trading_research.data.prices -- uses fixture JSON, no live network calls."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from trading_research.data.prices import PriceFetchError, fetch_price_snapshot

FIXTURE_CHART = {
    "chart": {
        "result": [
            {
                "meta": {
                    "regularMarketPrice": 150.0,
                    "fiftyTwoWeekHigh": 180.0,
                    "fiftyTwoWeekLow": 120.0,
                },
                "indicators": {
                    "quote": [
                        {
                            "close": [100.0 + i for i in range(60)],
                            "volume": [1_000_000 + (i * 1000) for i in range(60)],
                        }
                    ]
                },
            }
        ],
        "error": None,
    }
}


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_fetch_price_snapshot_computes_technicals():
    with patch("urllib.request.urlopen", return_value=_FakeResponse(FIXTURE_CHART)):
        snapshot = fetch_price_snapshot("AAPL")

    assert snapshot.ticker == "AAPL"
    assert snapshot.last_close == 150.0
    assert snapshot.fifty_two_week_high == 180.0
    assert snapshot.above_sma_50 is True
    assert "AAPL" in snapshot.technical_summary()
    assert "volatility" in snapshot.risk_summary().lower()


def test_fetch_price_snapshot_raises_on_empty_result():
    empty = {"chart": {"result": [], "error": None}}
    with patch("urllib.request.urlopen", return_value=_FakeResponse(empty)):
        with pytest.raises(PriceFetchError):
            fetch_price_snapshot("BADTICKER")


def test_fetch_price_snapshot_raises_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        with pytest.raises(PriceFetchError):
            fetch_price_snapshot("AAPL")
