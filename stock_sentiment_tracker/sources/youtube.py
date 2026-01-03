from __future__ import annotations

from datetime import datetime, timezone

from googleapiclient.discovery import build

from stock_sentiment_tracker.config import APIKeys
from stock_sentiment_tracker.models import TextItem
from stock_sentiment_tracker.sources.mock import mock_items
from stock_sentiment_tracker.utils import RateLimiter, clean_text


def _parse_rfc3339(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        # Example: 2024-01-01T12:34:56Z
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_youtube_comments(
    ticker: str,
    company_name: str | None,
    keys: APIKeys,
    *,
    videos: int = 7,
    comments_per_video: int = 50,
    rate_limiter: RateLimiter | None = None,
) -> tuple[list[TextItem], list[str]]:
    """
    Search videos mentioning the ticker/company and fetch top comments.
    Returns (items, warnings).
    """
    warnings: list[str] = []
    if not keys.youtube_api_key:
        warnings.append("YouTube API key not configured; using mock YouTube data.")
        return mock_items("YouTube", ticker), warnings

    limiter = rate_limiter or RateLimiter(min_interval_seconds=1.0)
    items: list[TextItem] = []

    q = f"{ticker.upper()} stock analysis"
    if company_name and company_name.strip():
        q = f"{ticker.upper()} {company_name.strip()} stock analysis"

    try:
        yt = build("youtube", "v3", developerKey=keys.youtube_api_key)

        limiter.wait()
        search_resp = (
            yt.search()
            .list(part="id,snippet", q=q, type="video", maxResults=max(1, min(10, videos)))
            .execute()
        )
        video_ids: list[str] = []
        for it in search_resp.get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                video_ids.append(vid)

        for vid in video_ids[:videos]:
            fetched = 0
            page_token: str | None = None
            while fetched < comments_per_video:
                limiter.wait()
                req = yt.commentThreads().list(
                    part="snippet",
                    videoId=vid,
                    maxResults=min(100, comments_per_video - fetched),
                    pageToken=page_token,
                    textFormat="plainText",
                )
                resp = req.execute()
                for th in resp.get("items", []):
                    top = ((th.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
                    txt = clean_text(top.get("textDisplay", "") or "")
                    if not txt:
                        continue
                    published = _parse_rfc3339(top.get("publishedAt"))
                    author = top.get("authorDisplayName")
                    items.append(
                        TextItem(
                            platform="YouTube",
                            text=txt,
                            created_at=published,
                            url=f"https://www.youtube.com/watch?v={vid}",
                            author=author,
                            external_id=(th.get("id") or None),
                            extra={"video_id": vid, "query": q},
                        )
                    )
                    fetched += 1
                    if fetched >= comments_per_video:
                        break
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

    except Exception as e:
        warnings.append(f"YouTube fetch failed ({type(e).__name__}); using mock YouTube data.")
        if not items:
            return mock_items("YouTube", ticker), warnings

    return items, warnings

