# Stock Sentiment Tracker

Streamlit web app for analyzing **social sentiment** around public equity tickers (e.g., `AAPL`, `TSLA`) using:

- **X (Twitter)** via Tweepy (API v2 recent search)
- **Reddit** via PRAW
- **YouTube** via `google-api-python-client`
- **Finnhub** social sentiment (aggregated Reddit + Twitter)
- **StockTwits** symbol stream (optional)

It applies **VADER sentiment** to each post/comment, then produces summary metrics, charts, a sample table, topic modeling (NMF), and positive/negative word clouds.

---

## Local setup

### 1) Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure API keys (choose one)

#### Option A: environment variables (local dev)

Copy/paste into your shell profile, or export in the terminal before running:

```bash
# X (Twitter) - choose either bearer-only OR full key set
export TWITTER_BEARER_TOKEN="..."
# OR:
export TWITTER_CONSUMER_KEY="..."
export TWITTER_CONSUMER_SECRET="..."
export TWITTER_ACCESS_TOKEN="..."
export TWITTER_ACCESS_TOKEN_SECRET="..."

# Reddit (PRAW)
export REDDIT_CLIENT_ID="..."
export REDDIT_CLIENT_SECRET="..."
export REDDIT_USER_AGENT="stock-sentiment-tracker/1.0 by <your-username>"

# YouTube Data API v3
export YOUTUBE_API_KEY="..."

# Finnhub
export FINNHUB_API_KEY="..."

# StockTwits (optional; many endpoints work without a key)
export STOCKTWITS_TOKEN="..."
```

#### Option B: Streamlit secrets (recommended for deploy)

Create `.streamlit/secrets.toml` (do not commit it). Start from:

- `.streamlit/secrets.toml.example`

---

## Run the app

```bash
streamlit run app.py
```

On first run, the app may download required NLTK resources (`vader_lexicon`, `punkt`, `stopwords`).

---

## Deploy (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create a new app and select:
   - **Repository**: this repo
   - **Branch**: `main`
   - **Main file path**: `app.py`
3. Add your keys in **App settings → Secrets**, using the same names as in `.streamlit/secrets.toml.example`.

---

## Where to get free API keys

- **X (Twitter)**: Developer portal → create a project/app → generate tokens  
  Docs: `https://developer.x.com/en/docs`
- **Reddit**: create an app at `https://www.reddit.com/prefs/apps` (script app works for read-only searches)
- **YouTube**: Google Cloud Console → enable YouTube Data API v3 → create API key  
  Docs: `https://developers.google.com/youtube/v3`
- **Finnhub**: create a free account and key  
  Docs: `https://finnhub.io/docs/api`
- **StockTwits**: symbol stream often works without auth; tokens vary by plan  
  Docs: `https://api.stocktwits.com/developers/docs`