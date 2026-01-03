from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TextItem:
    """Normalized text item from any platform."""

    platform: str
    text: str
    created_at: datetime | None = None
    url: str | None = None
    author: str | None = None
    external_id: str | None = None
    extra: dict | None = None

