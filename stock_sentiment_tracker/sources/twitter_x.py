from __future__ import annotations

from datetime import timezone

import tweepy

from stock_sentiment_tracker.config import APIKeys
from stock_sentiment_tracker.models import TextItem
from stock_sentiment_tracker.sources.mock import mock_items
from stock_sentiment_tracker.utils import RateLimiter, clean_text


def _build_client(keys: APIKeys) -> tweepy.Client | None:
    """
    Tweepy supports Twitter API v2 via tweepy.Client.

    Auth options:
    - Bearer token only (recommended for recent search)
    - OAuth1 keys (consumer + access tokens)
    """
    if keys.twitter_bearer_token:
        return tweepy.Client(bearer_token=keys.twitter_bearer_token, wait_on_rate_limit=False)

    if (
        keys.twitter_consumer_key
        and keys.twitter_consumer_secret
        and keys.twitter_access_token
        and keys.twitter_access_token_secret
    ):
        return tweepy.Client(
            consumer_key=keys.twitter_consumer_key,
            consumer_secret=keys.twitter_consumer_secret,
            access_token=keys.twitter_access_token,
            access_token_secret=keys.twitter_access_token_secret,
            wait_on_rate_limit=False,
        )
    return None


def fetch_recent_tweets(
    ticker: str,
    company_name: str | None,
    keys: APIKeys,
    *,
    limit: int = 150,
    rate_limiter: RateLimiter | None = None,
) -> tuple[list[TextItem], list[str]]:
    """
    Search recent tweets containing $TICKER or company name.
    Returns (items, warnings).
    """
    warnings: list[str] = []
    client = _build_client(keys)
    if client is None:
        warnings.append("X (Twitter) keys not configured; using mock X data.")
        return mock_items("X", ticker), warnings

    # Twitter recent search max_results is 10..100 per request; paginate.
    cashtag = f"${ticker.upper()}"
    query_parts = [f'("{cashtag}")']
    if company_name and company_name.strip():
        query_parts.append(f'"{company_name.strip()}"')
    query = " OR ".join(query_parts) + " -is:retweet lang:en"

    items: list[TextItem] = []
    next_token: str | None = None
    limiter = rate_limiter or RateLimiter(min_interval_seconds=1.2)

    try:
        while len(items) < limit:
            limiter.wait()
            remaining = limit - len(items)
            max_results = 100 if remaining >= 100 else max(10, remaining)
            resp = client.search_recent_tweets(
                query=query,
                max_results=max_results,
                next_token=next_token,
                tweet_fields=["created_at", "lang"],
            )

            if resp is None or resp.data is None:
                break

            for tw in resp.data:
                txt = clean_text(getattr(tw, "text", "") or "")
                if not txt:
                    continue
                created_at = getattr(tw, "created_at", None)
                if created_at is not None and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                items.append(
                    TextItem(
                        platform="X",
                        text=txt,
                        created_at=created_at,
                        url=f"https://x.com/i/web/status/{tw.id}",
                        author=None,
                        external_id=str(tw.id),
                        extra={"query": query},
                    )
                )

            meta = getattr(resp, "meta", None) or {}
            next_token = meta.get("next_token")
            if not next_token:
                break

    except tweepy.TooManyRequests:
        warnings.append("X rate limit hit; using mock X data for remaining results.")
        if not items:
            return mock_items("X", ticker), warnings
    except Exception as e:
        warnings.append(f"X fetch failed ({type(e).__name__}); using mock X data.")
        if not items:
            return mock_items("X", ticker), warnings

    return items, warnings

