from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import requests

from stock_sentiment_tracker.config import APIKeys
from stock_sentiment_tracker.utils import RateLimiter


@dataclass(frozen=True)
class FinnhubSocialSentiment:
    """
    Finnhub provides *aggregated* sentiment (not raw post text),
    so we treat it separately from VADER-per-post analysis.
    """

    symbol: str
    reddit_mentions: int = 0
    reddit_positive_score: float = 0.0
    reddit_negative_score: float = 0.0
    twitter_mentions: int = 0
    twitter_positive_score: float = 0.0
    twitter_negative_score: float = 0.0


def fetch_finnhub_social_sentiment(
    ticker: str,
    keys: APIKeys,
    *,
    days: int = 7,
    rate_limiter: RateLimiter | None = None,
) -> tuple[FinnhubSocialSentiment | None, list[str]]:
    warnings: list[str] = []
    if not keys.finnhub_api_key:
        warnings.append("Finnhub API key not configured; skipping Finnhub aggregated sentiment.")
        return None, warnings

    limiter = rate_limiter or RateLimiter(min_interval_seconds=0.8)
    limiter.wait()

    to_d = date.today()
    from_d = to_d - timedelta(days=max(1, days))
    url = "https://finnhub.io/api/v1/stock/social-sentiment"
    params = {
        "symbol": ticker.upper(),
        "from": from_d.isoformat(),
        "to": to_d.isoformat(),
        "token": keys.finnhub_api_key,
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 429:
            warnings.append("Finnhub rate limit hit; skipping Finnhub aggregated sentiment.")
            return None, warnings
        r.raise_for_status()
        data = r.json() or {}
        reddit = (data.get("reddit") or [])[-1:]  # last datapoint
        twitter = (data.get("twitter") or [])[-1:]

        def _sum_field(rows: list[dict], field: str) -> float:
            total = 0.0
            for row in rows:
                try:
                    total += float(row.get(field) or 0.0)
                except Exception:
                    continue
            return total

        def _sum_int(rows: list[dict], field: str) -> int:
            total = 0
            for row in rows:
                try:
                    total += int(row.get(field) or 0)
                except Exception:
                    continue
            return total

        fh = FinnhubSocialSentiment(
            symbol=ticker.upper(),
            reddit_mentions=_sum_int(reddit, "mention"),
            reddit_positive_score=_sum_field(reddit, "positiveScore"),
            reddit_negative_score=_sum_field(reddit, "negativeScore"),
            twitter_mentions=_sum_int(twitter, "mention"),
            twitter_positive_score=_sum_field(twitter, "positiveScore"),
            twitter_negative_score=_sum_field(twitter, "negativeScore"),
        )
        return fh, warnings
    except Exception as e:
        warnings.append(f"Finnhub fetch failed ({type(e).__name__}); skipping Finnhub aggregated sentiment.")
        return None, warnings

