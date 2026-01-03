from __future__ import annotations
from dataclasses import dataclass

import nltk
import pandas as pd
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from wordcloud import WordCloud

from stock_sentiment_tracker.models import TextItem
from stock_sentiment_tracker.utils import clean_text


def ensure_nltk() -> None:
    """
    Downloads required NLTK data if missing.
    This is safe to run multiple times.
    """
    required = {
        "vader_lexicon": "sentiment/vader_lexicon",
        "punkt": "tokenizers/punkt",
        "stopwords": "corpora/stopwords",
    }
    for pkg, path in required.items():
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)


def vader_analyzer() -> SentimentIntensityAnalyzer:
    ensure_nltk()
    return SentimentIntensityAnalyzer()


def analyze_items(items: list[TextItem]) -> pd.DataFrame:
    """
    Convert items to a dataframe and apply VADER to each row.
    """
    sia = vader_analyzer()
    rows: list[dict] = []
    for it in items:
        txt = clean_text(it.text)
        if not txt:
            continue
        scores = sia.polarity_scores(txt)
        rows.append(
            {
                "platform": it.platform,
                "created_at": it.created_at,
                "text": txt,
                "url": it.url,
                "author": it.author,
                "external_id": it.external_id,
                "compound": float(scores.get("compound", 0.0)),
                "pos": float(scores.get("pos", 0.0)),
                "neu": float(scores.get("neu", 0.0)),
                "neg": float(scores.get("neg", 0.0)),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty and "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    return df


def label_sentiment(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


@dataclass(frozen=True)
class SummaryMetrics:
    mention_count: int
    avg_compound: float
    pct_positive: float
    pct_negative: float
    pct_neutral: float


def summarize(df: pd.DataFrame) -> SummaryMetrics:
    if df is None or df.empty:
        return SummaryMetrics(mention_count=0, avg_compound=0.0, pct_positive=0.0, pct_negative=0.0, pct_neutral=0.0)
    mention_count = int(len(df))
    avg_compound = float(df["compound"].mean()) if "compound" in df.columns else 0.0
    labels = df["compound"].apply(label_sentiment)
    counts = labels.value_counts(dropna=False).to_dict()
    pct_positive = 100.0 * float(counts.get("positive", 0)) / mention_count
    pct_negative = 100.0 * float(counts.get("negative", 0)) / mention_count
    pct_neutral = 100.0 * float(counts.get("neutral", 0)) / mention_count
    return SummaryMetrics(
        mention_count=mention_count,
        avg_compound=avg_compound,
        pct_positive=pct_positive,
        pct_negative=pct_negative,
        pct_neutral=pct_neutral,
    )


def platform_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["platform", "mentions", "avg_compound"])
    out = (
        df.groupby("platform", as_index=False)
        .agg(mentions=("text", "count"), avg_compound=("compound", "mean"))
        .sort_values("mentions", ascending=False)
    )
    out["avg_compound"] = out["avg_compound"].astype(float)
    return out


def distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame([{"sentiment": "positive", "count": 0}, {"sentiment": "neutral", "count": 0}, {"sentiment": "negative", "count": 0}])
    labels = df["compound"].apply(label_sentiment)
    counts = labels.value_counts().reindex(["positive", "neutral", "negative"], fill_value=0)
    return pd.DataFrame({"sentiment": counts.index, "count": counts.values})


def time_series(df: pd.DataFrame, freq: str = "D") -> pd.DataFrame:
    """
    Sentiment over time (avg compound), if timestamps exist.
    freq: 'H', 'D', 'W'...
    """
    if df is None or df.empty or "created_at" not in df.columns:
        return pd.DataFrame(columns=["time", "avg_compound", "mentions"])
    d = df.dropna(subset=["created_at"]).copy()
    if d.empty:
        return pd.DataFrame(columns=["time", "avg_compound", "mentions"])
    d = d.set_index("created_at").sort_index()
    out = d.resample(freq).agg(avg_compound=("compound", "mean"), mentions=("text", "count")).reset_index()
    out = out.rename(columns={"created_at": "time"})
    return out


def topics_nmf(texts: list[str], *, n_topics: int = 6, top_words: int = 8, max_features: int = 2000) -> list[dict]:
    """
    Topic modeling using TF-IDF + NMF.
    Returns a list of topic dicts: {topic: int, terms: [..]}.
    """
    docs = [clean_text(t) for t in texts if isinstance(t, str) and clean_text(t)]
    if len(docs) < 10:
        return []

    n_topics = max(2, min(int(n_topics), 10))
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=max_features,
        ngram_range=(1, 2),
        min_df=2,
    )
    X = vectorizer.fit_transform(docs)
    if X.shape[1] < 10:
        return []

    model = NMF(n_components=n_topics, random_state=42, init="nndsvda", max_iter=400)
    W = model.fit_transform(X)
    H = model.components_
    feature_names = vectorizer.get_feature_names_out()

    topics: list[dict] = []
    for i, row in enumerate(H):
        top_idx = row.argsort()[::-1][:top_words]
        terms = [feature_names[j] for j in top_idx]
        topics.append({"topic": i + 1, "terms": terms})
    # If NMF fails silently, ensure result isn't nonsense
    if any(len(t["terms"]) == 0 for t in topics):
        return []
    return topics


def build_wordcloud(texts: list[str], *, width: int = 900, height: int = 450) -> WordCloud | None:
    joined = " ".join([clean_text(t) for t in texts if isinstance(t, str) and clean_text(t)])
    if len(joined) < 50:
        return None
    wc = WordCloud(width=width, height=height, background_color="white", collocations=False)
    return wc.generate(joined)

