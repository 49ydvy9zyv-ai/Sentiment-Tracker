from __future__ import annotations

from datetime import datetime, timezone

import requests

from stock_sentiment_tracker.config import APIKeys
from stock_sentiment_tracker.models import TextItem
from stock_sentiment_tracker.sources.mock import mock_items
from stock_sentiment_tracker.utils import RateLimiter, clean_text


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_stocktwits(
    ticker: str,
    keys: APIKeys,
    *,
    limit: int = 80,
    rate_limiter: RateLimiter | None = None,
) -> tuple[list[TextItem], list[str]]:
    """
    Fetch StockTwits symbol stream messages.

    Many StockTwits endpoints allow unauthenticated reads. If you have a token,
    provide STOCKTWITS_TOKEN to increase reliability.
    """
    warnings: list[str] = []
    limiter = rate_limiter or RateLimiter(min_interval_seconds=0.7)

    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker.upper()}.json"
    params = {}
    if keys.stocktwits_token:
        params["access_token"] = keys.stocktwits_token

    items: list[TextItem] = []
    try:
        limiter.wait()
        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 429:
            warnings.append("StockTwits rate limit hit; using mock StockTwits data.")
            return mock_items("StockTwits", ticker), warnings
        r.raise_for_status()
        data = r.json() or {}
        for msg in (data.get("messages") or [])[:limit]:
            body = clean_text((msg.get("body") or "")[:5000])
            if not body:
                continue
            created_at = _parse_iso(msg.get("created_at"))
            user = (msg.get("user") or {}).get("username")
            mid = msg.get("id")
            items.append(
                TextItem(
                    platform="StockTwits",
                    text=body,
                    created_at=created_at,
                    url=f"https://stocktwits.com/message/{mid}" if mid else None,
                    author=user,
                    external_id=str(mid) if mid else None,
                    extra={"symbol": ticker.upper()},
                )
            )
    except Exception as e:
        warnings.append(f"StockTwits fetch failed ({type(e).__name__}); using mock StockTwits data.")
        if not items:
            return mock_items("StockTwits", ticker), warnings

    return items, warnings

