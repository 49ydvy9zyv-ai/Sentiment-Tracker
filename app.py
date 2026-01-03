from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from stock_sentiment_tracker.analysis import (
    build_wordcloud,
    distribution,
    platform_breakdown,
    summarize,
    time_series,
    topics_nmf,
    analyze_items,
)
from stock_sentiment_tracker.config import APIKeys
from stock_sentiment_tracker.pipeline import fetch_all
from stock_sentiment_tracker.utils import ensure_ticker


st.set_page_config(page_title="Stock Sentiment Tracker", page_icon="📈", layout="wide")

st.title("Stock Sentiment Tracker")
st.caption("Analyze social sentiment for public equity tickers across X, Reddit, YouTube, Finnhub, and StockTwits.")


def _keys_status(keys: APIKeys) -> dict[str, bool]:
    return {
        "TWITTER_BEARER_TOKEN": bool(keys.twitter_bearer_token),
        "TWITTER_OAUTH1_SET": bool(
            keys.twitter_consumer_key
            and keys.twitter_consumer_secret
            and keys.twitter_access_token
            and keys.twitter_access_token_secret
        ),
        "REDDIT_KEYS": bool(keys.reddit_client_id and keys.reddit_client_secret and keys.reddit_user_agent),
        "YOUTUBE_API_KEY": bool(keys.youtube_api_key),
        "FINNHUB_API_KEY": bool(keys.finnhub_api_key),
        "STOCKTWITS_TOKEN": bool(keys.stocktwits_token),
    }


@st.cache_data(ttl=600, show_spinner=False)
def _run_fetch_and_analyze(
    ticker: str,
    company_name: str,
    x_limit: int,
    reddit_posts_per_sub: int,
    reddit_comments_per_post: int,
    youtube_videos: int,
    youtube_comments_per_video: int,
    enable_stocktwits: bool,
    stocktwits_limit: int,
    enable_finnhub: bool,
    finnhub_days: int,
    # cache_bust can be changed to force rerun without leaking secrets
    cache_bust: int,
) -> tuple[pd.DataFrame, list[str], dict | None]:
    keys = APIKeys.load()
    result = fetch_all(
        ticker=ticker,
        company_name=company_name or None,
        keys=keys,
        x_limit=x_limit,
        reddit_posts_per_sub=reddit_posts_per_sub,
        reddit_comments_per_post=reddit_comments_per_post,
        youtube_videos=youtube_videos,
        youtube_comments_per_video=youtube_comments_per_video,
        enable_stocktwits=enable_stocktwits,
        stocktwits_limit=stocktwits_limit,
        enable_finnhub=enable_finnhub,
        finnhub_days=finnhub_days,
    )
    df = analyze_items(result.items)
    finnhub = None
    if result.finnhub is not None:
        finnhub = {
            "symbol": result.finnhub.symbol,
            "reddit_mentions": result.finnhub.reddit_mentions,
            "reddit_positive_score": result.finnhub.reddit_positive_score,
            "reddit_negative_score": result.finnhub.reddit_negative_score,
            "twitter_mentions": result.finnhub.twitter_mentions,
            "twitter_positive_score": result.finnhub.twitter_positive_score,
            "twitter_negative_score": result.finnhub.twitter_negative_score,
        }
    return df, result.warnings, finnhub


with st.sidebar:
    st.subheader("Inputs")
    ticker_in = st.text_input("Stock ticker", value="AAPL", help="Example: AAPL, TSLA, MSFT")
    company_in = st.text_input("Company name (optional)", value="", help="Used as an extra search term.")

    st.divider()
    st.subheader("Collection limits")
    x_limit = st.slider("X (Twitter) tweets", 50, 200, 150, 10)
    reddit_posts_per_sub = st.slider("Reddit posts per subreddit", 10, 60, 25, 5)
    reddit_comments_per_post = st.slider("Reddit comments per post", 0, 30, 8, 1)
    youtube_videos = st.slider("YouTube videos to scan", 3, 10, 7, 1)
    youtube_comments_per_video = st.slider("YouTube comments per video", 10, 100, 50, 5)

    st.divider()
    st.subheader("Optional sources")
    enable_stocktwits = st.checkbox("Enable StockTwits", value=True)
    stocktwits_limit = st.slider("StockTwits messages", 20, 150, 80, 10)
    enable_finnhub = st.checkbox("Enable Finnhub aggregated sentiment", value=True)
    finnhub_days = st.slider("Finnhub window (days)", 3, 30, 7, 1)

    st.divider()
    st.subheader("API key status")
    keys = APIKeys.load()
    statuses = _keys_status(keys)
    for k, ok in statuses.items():
        st.write(f"- {'✅' if ok else '❌'} `{k}`")
    st.caption("Add secrets via `.streamlit/secrets.toml` or environment variables. See `README.md`.")

    st.divider()
    cache_bust = st.number_input("Cache bust (increment to force refresh)", min_value=0, value=0, step=1)
    if st.button("Clear Streamlit cache"):
        st.cache_data.clear()
        st.success("Cache cleared.")


ticker = ensure_ticker(ticker_in)
if not ticker:
    st.error("Enter a valid ticker (letters/numbers only).")
    st.stop()

run = st.button("Fetch & Analyze", type="primary")

if run:
    with st.spinner("Fetching data and running sentiment analysis..."):
        df, warnings, finnhub = _run_fetch_and_analyze(
            ticker=ticker,
            company_name=company_in.strip(),
            x_limit=int(x_limit),
            reddit_posts_per_sub=int(reddit_posts_per_sub),
            reddit_comments_per_post=int(reddit_comments_per_post),
            youtube_videos=int(youtube_videos),
            youtube_comments_per_video=int(youtube_comments_per_video),
            enable_stocktwits=bool(enable_stocktwits),
            stocktwits_limit=int(stocktwits_limit),
            enable_finnhub=bool(enable_finnhub),
            finnhub_days=int(finnhub_days),
            cache_bust=int(cache_bust),
        )

    for w in warnings:
        st.warning(w)

    if df.empty:
        st.info("No text items were collected. Try increasing limits or adding API keys.")
        st.stop()

    summary = summarize(df)
    breakdown = platform_breakdown(df)
    dist = distribution(df)
    ts = time_series(df, freq="D")

    # ---- Summary ----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total mentions", f"{summary.mention_count:,}")
    c2.metric("Avg compound", f"{summary.avg_compound:+.3f}")
    c3.metric("% positive", f"{summary.pct_positive:.1f}%")
    c4.metric("% negative", f"{summary.pct_negative:.1f}%")

    gauge_color = "#16a34a" if summary.avg_compound >= 0 else "#dc2626"
    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=float(summary.avg_compound),
            number={"valueformat": "+.3f"},
            gauge={
                "axis": {"range": [-1, 1]},
                "bar": {"color": gauge_color},
                "steps": [
                    {"range": [-1, -0.05], "color": "#fee2e2"},
                    {"range": [-0.05, 0.05], "color": "#f3f4f6"},
                    {"range": [0.05, 1], "color": "#dcfce7"},
                ],
                "threshold": {"line": {"color": "black", "width": 2}, "thickness": 0.75, "value": 0.0},
            },
            title={"text": "Overall sentiment (VADER compound)"},
        )
    )
    fig_gauge.update_layout(height=260, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_gauge, use_container_width=True)

    # Finnhub summary (aggregated)
    if finnhub is not None:
        with st.expander("Finnhub aggregated sentiment (not VADER-per-post)"):
            st.write(
                {
                    "symbol": finnhub["symbol"],
                    "reddit_mentions": finnhub["reddit_mentions"],
                    "reddit_positive_score": finnhub["reddit_positive_score"],
                    "reddit_negative_score": finnhub["reddit_negative_score"],
                    "twitter_mentions": finnhub["twitter_mentions"],
                    "twitter_positive_score": finnhub["twitter_positive_score"],
                    "twitter_negative_score": finnhub["twitter_negative_score"],
                }
            )

    st.divider()

    # ---- Visualizations ----
    v1, v2 = st.columns(2)
    with v1:
        fig_bar = px.bar(
            breakdown,
            x="platform",
            y="avg_compound",
            color="mentions",
            title="Sentiment by platform (avg compound)",
            labels={"avg_compound": "Avg compound", "mentions": "Mentions"},
        )
        fig_bar.update_layout(height=380)
        st.plotly_chart(fig_bar, use_container_width=True)

    with v2:
        fig_pie = px.pie(dist, names="sentiment", values="count", title="Sentiment distribution")
        fig_pie.update_layout(height=380)
        st.plotly_chart(fig_pie, use_container_width=True)

    if not ts.empty:
        fig_line = px.line(ts, x="time", y="avg_compound", markers=True, title="Sentiment over time (avg compound)")
        fig_line.update_layout(height=340)
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No timestamps available to plot sentiment over time.")

    st.divider()

    # ---- Topics + Word clouds ----
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Topic modeling (NMF)")
        n_topics = st.slider("Topics", 5, 10, 6, 1)
        topics = topics_nmf(df["text"].tolist(), n_topics=int(n_topics), top_words=8)
        if not topics:
            st.info("Not enough text to extract stable topics yet.")
        else:
            for t in topics:
                st.write(f"**Topic {t['topic']}**: " + ", ".join(t["terms"]))

    with right:
        st.subheader("Word clouds")
        pos_texts = df.loc[df["compound"] >= 0.05, "text"].tolist()
        neg_texts = df.loc[df["compound"] <= -0.05, "text"].tolist()
        wc_pos = build_wordcloud(pos_texts)
        wc_neg = build_wordcloud(neg_texts)

        cpos, cneg = st.columns(2)
        with cpos:
            st.caption("Positive")
            if wc_pos is None:
                st.info("Not enough positive text.")
            else:
                st.image(wc_pos.to_array(), use_container_width=True)
        with cneg:
            st.caption("Negative")
            if wc_neg is None:
                st.info("Not enough negative text.")
            else:
                st.image(wc_neg.to_array(), use_container_width=True)

    st.divider()

    # ---- Sample table + export ----
    st.subheader("Sample posts/comments with sentiment")
    show_n = st.slider("Rows to display", 20, 300, 100, 10)
    view = df.sort_values("compound", ascending=False).head(int(show_n))
    st.dataframe(
        view[["platform", "created_at", "compound", "pos", "neu", "neg", "text", "url"]],
        use_container_width=True,
        height=420,
    )

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download all results as CSV",
        data=csv_bytes,
        file_name=f"{ticker}_sentiment.csv",
        mime="text/csv",
    )

else:
    st.info("Enter a ticker and click **Fetch & Analyze**.")

