from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone


_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WS_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """
    Light cleanup suitable for VADER + topic modeling.
    Keep cashtags ($AAPL) and tickers; just remove urls and normalize whitespace.
    """
    text = _URL_RE.sub("", text or "")
    text = text.replace("\u200b", " ")
    text = _WS_RE.sub(" ", text).strip()
    return text


def utc_from_epoch(seconds: float | int) -> datetime:
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc)


def ensure_ticker(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    return re.sub(r"[^A-Z0-9\.\-]", "", t)


@dataclass
class RateLimiter:
    """
    Minimal, per-source rate limiting.
    Not a strict API quota manager, but helps avoid bursts.
    """

    min_interval_seconds: float = 1.0
    _last_ts: float = 0.0

    def wait(self) -> None:
        now = time.time()
        elapsed = now - self._last_ts
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_ts = time.time()

