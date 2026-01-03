from __future__ import annotations

import praw

from stock_sentiment_tracker.config import APIKeys
from stock_sentiment_tracker.models import TextItem
from stock_sentiment_tracker.sources.mock import mock_items
from stock_sentiment_tracker.utils import RateLimiter, clean_text, utc_from_epoch


DEFAULT_SUBREDDITS = ["stocks", "investing", "wallstreetbets"]


def _build_reddit(keys: APIKeys) -> praw.Reddit | None:
    if keys.reddit_client_id and keys.reddit_client_secret and keys.reddit_user_agent:
        return praw.Reddit(
            client_id=keys.reddit_client_id,
            client_secret=keys.reddit_client_secret,
            user_agent=keys.reddit_user_agent,
            check_for_async=False,
        )
    return None


def fetch_reddit(
    ticker: str,
    company_name: str | None,
    keys: APIKeys,
    *,
    subreddits: list[str] | None = None,
    posts_per_subreddit: int = 30,
    comments_per_post: int = 10,
    rate_limiter: RateLimiter | None = None,
) -> tuple[list[TextItem], list[str]]:
    """
    Search a few finance subreddits for ticker/company and pull top-level comments.
    Returns (items, warnings).
    """
    warnings: list[str] = []
    reddit = _build_reddit(keys)
    if reddit is None:
        warnings.append("Reddit keys not configured; using mock Reddit data.")
        return mock_items("Reddit", ticker), warnings

    subs = subreddits or DEFAULT_SUBREDDITS
    query_parts = [ticker.upper(), f"${ticker.upper()}"]
    if company_name and company_name.strip():
        query_parts.append(company_name.strip())
    query = " OR ".join(f'"{p}"' for p in query_parts)

    items: list[TextItem] = []
    limiter = rate_limiter or RateLimiter(min_interval_seconds=1.0)

    try:
        for sub in subs:
            limiter.wait()
            subreddit = reddit.subreddit(sub)

            # PRAW's search uses Reddit listing; limit is approximate.
            for submission in subreddit.search(query, sort="hot", time_filter="week", limit=posts_per_subreddit):
                title = clean_text(submission.title or "")
                body = clean_text(submission.selftext or "")
                combined = (title + "\n" + body).strip()
                created_at = utc_from_epoch(getattr(submission, "created_utc", 0) or 0)
                url = getattr(submission, "url", None) or f"https://www.reddit.com{submission.permalink}"

                if combined:
                    items.append(
                        TextItem(
                            platform="Reddit",
                            text=combined,
                            created_at=created_at,
                            url=url,
                            author=str(getattr(submission, "author", "") or ""),
                            external_id=str(submission.id),
                            extra={"subreddit": sub, "kind": "post"},
                        )
                    )

                # Comments
                limiter.wait()
                try:
                    submission.comments.replace_more(limit=0)
                    count = 0
                    for c in submission.comments.list():
                        if count >= comments_per_post:
                            break
                        txt = clean_text(getattr(c, "body", "") or "")
                        if not txt:
                            continue
                        c_created = utc_from_epoch(getattr(c, "created_utc", 0) or 0)
                        items.append(
                            TextItem(
                                platform="Reddit",
                                text=txt,
                                created_at=c_created,
                                url=f"https://www.reddit.com{c.permalink}",
                                author=str(getattr(c, "author", "") or ""),
                                external_id=str(getattr(c, "id", "") or ""),
                                extra={"subreddit": sub, "kind": "comment", "post_id": submission.id},
                            )
                        )
                        count += 1
                except Exception:
                    # Comments may fail on some locked/deleted threads; keep going.
                    continue

    except praw.exceptions.APIException:
        warnings.append("Reddit API error/rate limit hit; using mock Reddit data.")
        if not items:
            return mock_items("Reddit", ticker), warnings
    except Exception as e:
        warnings.append(f"Reddit fetch failed ({type(e).__name__}); using mock Reddit data.")
        if not items:
            return mock_items("Reddit", ticker), warnings

    return items, warnings

