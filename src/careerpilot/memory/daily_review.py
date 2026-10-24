from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DailyReviewDraft:
    local_date: str
    wins: tuple[str, ...]
    ideas: tuple[str, ...]
    blockers: tuple[str, ...]
    open_loops: tuple[str, ...]
    tomorrow_step: str | None
    source_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DailyReview:
    id: str
    owner_id: str
    local_date: str
    wins: tuple[str, ...]
    ideas: tuple[str, ...]
    blockers: tuple[str, ...]
    open_loops: tuple[str, ...]
    tomorrow_step: str | None
    source_event_ids: tuple[str, ...]
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
