from __future__ import annotations

import uuid
from dataclasses import dataclass

SESSION_COOKIE_NAME = "careerpilot_session"


@dataclass(frozen=True, slots=True)
class Identity:
    owner_id: str
    conversation_id: str | None = None
    is_anonymous: bool = False


def generate_conversation_id() -> str:
    try:
        return str(uuid.uuid7())
    except AttributeError:  # Python <3.14 fallback
        return str(uuid.uuid4())
