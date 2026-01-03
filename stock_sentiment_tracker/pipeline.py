from __future__ import annotations

from dataclasses import dataclass

from stock_sentiment_tracker.config import APIKeys
from stock_sentiment_tracker.models import TextItem
from stock_sentiment_tracker.sources.finnhub import FinnhubSocialSentiment, fetch_finnhub_social_sentiment
from stock_sentiment_tracker.sources.reddit import fetch_reddit
from stock_sentiment_tracker.sources.stocktwits import fetch_stocktwits
from stock_sentiment_tracker.sources.twitter_x import fetch_recent_tweets
from stock_sentiment_tracker.sources.youtube import fetch_youtube_comments
from stock_sentiment_tracker.utils import RateLimiter


@dataclass(frozen=True)
class FetchResult:
    items: list[TextItem]
    warnings: list[str]
    finnhub: FinnhubSocialSentiment | None = None


def _dedupe(items: list[TextItem]) -> list[TextItem]:
    seen: set[str] = set()
    out: list[TextItem] = []
    for it in items:
        key = f"{it.platform}|{it.external_id or ''}|{it.url or ''}|{it.text[:200]}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def fetch_all(
    ticker: str,
    company_name: str | None,
    keys: APIKeys,
    *,
    x_limit: int = 150,
    reddit_posts_per_sub: int = 25,
    reddit_comments_per_post: int = 8,
    youtube_videos: int = 7,
    youtube_comments_per_video: int = 50,
    stocktwits_limit: int = 80,
    finnhub_days: int = 7,
    enable_stocktwits: bool = True,
    enable_finnhub: bool = True,
) -> FetchResult:
    warnings: list[str] = []
    items: list[TextItem] = []

    # Per-source limiters (keeps each API from being hammered)
    x_limiter = RateLimiter(min_interval_seconds=1.2)
    reddit_limiter = RateLimiter(min_interval_seconds=1.0)
    yt_limiter = RateLimiter(min_interval_seconds=1.0)
    st_limiter = RateLimiter(min_interval_seconds=0.7)
    fh_limiter = RateLimiter(min_interval_seconds=0.8)

    x_items, x_warn = fetch_recent_tweets(
        ticker, company_name, keys, limit=x_limit, rate_limiter=x_limiter
    )
    items.extend(x_items)
    warnings.extend(x_warn)

    r_items, r_warn = fetch_reddit(
        ticker,
        company_name,
        keys,
        posts_per_subreddit=reddit_posts_per_sub,
        comments_per_post=reddit_comments_per_post,
        rate_limiter=reddit_limiter,
    )
    items.extend(r_items)
    warnings.extend(r_warn)

    y_items, y_warn = fetch_youtube_comments(
        ticker,
        company_name,
        keys,
        videos=youtube_videos,
        comments_per_video=youtube_comments_per_video,
        rate_limiter=yt_limiter,
    )
    items.extend(y_items)
    warnings.extend(y_warn)

    if enable_stocktwits:
        s_items, s_warn = fetch_stocktwits(
            ticker, keys, limit=stocktwits_limit, rate_limiter=st_limiter
        )
        items.extend(s_items)
        warnings.extend(s_warn)

    finnhub: FinnhubSocialSentiment | None = None
    if enable_finnhub:
        finnhub, fh_warn = fetch_finnhub_social_sentiment(
            ticker, keys, days=finnhub_days, rate_limiter=fh_limiter
        )
        warnings.extend(fh_warn)

    items = _dedupe(items)
    return FetchResult(items=items, warnings=warnings, finnhub=finnhub)

