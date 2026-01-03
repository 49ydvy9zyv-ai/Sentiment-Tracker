from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st


def _get_secret(name: str) -> str | None:
    """
    Prefer Streamlit secrets, then environment variables.
    Streamlit Community Cloud uses st.secrets; local dev can use env vars.
    """
    try:
        val = st.secrets.get(name)  # type: ignore[attr-defined]
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        # st.secrets may not be configured (e.g., running as a plain script)
        pass
    val = os.environ.get(name)
    return val.strip() if isinstance(val, str) and val.strip() else None


@dataclass(frozen=True)
class APIKeys:
    # X (Twitter)
    twitter_bearer_token: str | None = None
    twitter_consumer_key: str | None = None
    twitter_consumer_secret: str | None = None
    twitter_access_token: str | None = None
    twitter_access_token_secret: str | None = None

    # Reddit
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None

    # YouTube
    youtube_api_key: str | None = None

    # Finnhub
    finnhub_api_key: str | None = None

    # StockTwits (optional)
    stocktwits_token: str | None = None

    @staticmethod
    def load() -> "APIKeys":
        return APIKeys(
            twitter_bearer_token=_get_secret("TWITTER_BEARER_TOKEN"),
            twitter_consumer_key=_get_secret("TWITTER_CONSUMER_KEY"),
            twitter_consumer_secret=_get_secret("TWITTER_CONSUMER_SECRET"),
            twitter_access_token=_get_secret("TWITTER_ACCESS_TOKEN"),
            twitter_access_token_secret=_get_secret("TWITTER_ACCESS_TOKEN_SECRET"),
            reddit_client_id=_get_secret("REDDIT_CLIENT_ID"),
            reddit_client_secret=_get_secret("REDDIT_CLIENT_SECRET"),
            reddit_user_agent=_get_secret("REDDIT_USER_AGENT"),
            youtube_api_key=_get_secret("YOUTUBE_API_KEY"),
            finnhub_api_key=_get_secret("FINNHUB_API_KEY"),
            stocktwits_token=_get_secret("STOCKTWITS_TOKEN"),
        )

