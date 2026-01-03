from __future__ import annotations

from datetime import datetime, timedelta, timezone

from stock_sentiment_tracker.models import TextItem


def mock_items(platform: str, ticker: str) -> list[TextItem]:
    """
    Used when API keys are missing or rate limits/errors occur.
    Keeps the app usable for demo/testing.
    """
    now = datetime.now(tz=timezone.utc)
    t = ticker.upper()
    samples = [
        f"${t} looks strong after earnings. Guidance was better than expected.",
        f"I'm worried {t} is overvalued here. Macro headwinds are real.",
        f"Neutral take: {t} might trade sideways until the next catalyst.",
        f"Bull case: {t} product cycle + margin expansion could drive upside.",
        f"Bear case: {t} competition increasing; watch revenue growth.",
    ]
    items: list[TextItem] = []
    for i, s in enumerate(samples):
        items.append(
            TextItem(
                platform=platform,
                text=s,
                created_at=now - timedelta(hours=i * 6),
                url=None,
                author="mock",
                external_id=f"mock-{platform}-{i}",
                extra={"mock": True},
            )
        )
    return items

