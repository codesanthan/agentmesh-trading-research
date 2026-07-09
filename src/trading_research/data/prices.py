"""Fetch and summarize price history from Yahoo Finance's public chart API.

No API key required -- this hits the same JSON endpoint the Yahoo Finance
website itself uses (`query1.finance.yahoo.com/v8/finance/chart/...`).
"""

from __future__ import annotations

import json
import statistics
import urllib.request
from dataclasses import dataclass, field

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
USER_AGENT = "Mozilla/5.0 (compatible; agentmesh-trading-research/0.1)"


class PriceFetchError(Exception):
    pass


@dataclass
class PriceSnapshot:
    ticker: str
    last_close: float
    period_change_pct: float
    sma_50: float | None
    above_sma_50: bool | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    annualized_volatility_pct: float
    recent_avg_volume: float
    prior_avg_volume: float
    volume_trend: str
    closes: list[float] = field(default_factory=list)

    def technical_summary(self) -> str:
        lines = [
            f"{self.ticker}: last close ${self.last_close:.2f}, "
            f"{self.period_change_pct:+.1f}% over the lookback window.",
        ]
        if self.sma_50 is not None:
            position = "above" if self.above_sma_50 else "below"
            lines.append(
                f"Price is {position} its 50-day moving average (${self.sma_50:.2f})."
            )
        if self.fifty_two_week_high is not None and self.fifty_two_week_low is not None:
            lines.append(
                f"52-week range: ${self.fifty_two_week_low:.2f} - ${self.fifty_two_week_high:.2f}."
            )
        lines.append(
            f"Volume trend: {self.volume_trend} "
            f"(recent avg {self.recent_avg_volume:,.0f} vs prior avg {self.prior_avg_volume:,.0f})."
        )
        lines.append(f"Annualized volatility: {self.annualized_volatility_pct:.1f}%.")
        return " ".join(lines)

    def risk_summary(self) -> str:
        vol = self.annualized_volatility_pct
        if vol >= 45:
            vol_band = "high"
        elif vol >= 25:
            vol_band = "moderate"
        else:
            vol_band = "low"
        lines = [
            f"Annualized volatility of {vol:.1f}% is in the {vol_band} band for a single-name equity.",
        ]
        if self.fifty_two_week_high and self.last_close:
            drawdown = (self.last_close - self.fifty_two_week_high) / self.fifty_two_week_high * 100
            lines.append(
                f"Currently {abs(drawdown):.1f}% below its 52-week high "
                f"of ${self.fifty_two_week_high:.2f}."
            )
        if self.volume_trend == "rising":
            lines.append(
                "Rising volume alongside price movement can signal conviction (or "
                "capitulation) -- worth confirming direction before treating it as a "
                "clean signal."
            )
        else:
            lines.append("No unusual volume spike detected in the lookback window.")
        lines.append(
            "This is a single-name volatility read only -- it does not account for "
            "portfolio-level correlation or concentration, which the caller should "
            "assess separately."
        )
        return " ".join(lines)


def fetch_price_snapshot(ticker: str, range_: str = "3mo", interval: str = "1d") -> PriceSnapshot:
    """Fetch daily OHLCV history for `ticker` and compute a technical snapshot."""
    url = CHART_URL.format(ticker=ticker.upper()) + f"?range={range_}&interval={interval}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read())
    except Exception as exc:  # noqa: BLE001 - surfaced as a typed error for the CLI
        raise PriceFetchError(f"Could not fetch price data for '{ticker}': {exc}") from exc

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise PriceFetchError(f"Yahoo Finance error for '{ticker}': {chart['error']}")

    results = chart.get("result") or []
    if not results:
        raise PriceFetchError(f"No price data returned for '{ticker}'")

    result = results[0]
    meta = result.get("meta", {})
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    closes_raw = quote.get("close") or []
    volumes_raw = quote.get("volume") or []

    closes = [c for c in closes_raw if c is not None]
    volumes = [v for v in volumes_raw if v is not None]

    if len(closes) < 2:
        raise PriceFetchError(f"Not enough price history returned for '{ticker}'")

    last_close = meta.get("regularMarketPrice", closes[-1])
    period_change_pct = (closes[-1] - closes[0]) / closes[0] * 100

    sma_50 = statistics.fmean(closes[-50:]) if len(closes) >= 50 else None
    above_sma_50 = (last_close > sma_50) if sma_50 is not None else None

    daily_returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    daily_vol = statistics.pstdev(daily_returns) if len(daily_returns) > 1 else 0.0
    annualized_volatility_pct = daily_vol * (252 ** 0.5) * 100

    if len(volumes) >= 10:
        half = len(volumes) // 2
        prior_avg_volume = statistics.fmean(volumes[:half])
        recent_avg_volume = statistics.fmean(volumes[half:])
    elif volumes:
        prior_avg_volume = recent_avg_volume = statistics.fmean(volumes)
    else:
        prior_avg_volume = recent_avg_volume = 0.0

    if prior_avg_volume and recent_avg_volume > prior_avg_volume * 1.15:
        volume_trend = "rising"
    elif prior_avg_volume and recent_avg_volume < prior_avg_volume * 0.85:
        volume_trend = "falling"
    else:
        volume_trend = "stable"

    return PriceSnapshot(
        ticker=ticker.upper(),
        last_close=last_close,
        period_change_pct=period_change_pct,
        sma_50=sma_50,
        above_sma_50=above_sma_50,
        fifty_two_week_high=meta.get("fiftyTwoWeekHigh"),
        fifty_two_week_low=meta.get("fiftyTwoWeekLow"),
        annualized_volatility_pct=annualized_volatility_pct,
        recent_avg_volume=recent_avg_volume,
        prior_avg_volume=prior_avg_volume,
        volume_trend=volume_trend,
        closes=closes,
    )
