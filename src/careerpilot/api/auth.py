"""Anonymous user identity layer.

CareerPilot treats every visitor as a distinct anonymous user before
login is wired up. The server issues a random UUID on first visit and
stores it in an HttpOnly, Secure cookie. Downstream layers (chat, RAG,
cognitive store, personal documents) receive ``owner_id`` from this
module only — never from client input.

The same identity can later be bound to a real account without
changing any downstream data model, because ``owner_id`` is already
just a stable identifier.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Response

COOKIE_NAME = "careerpilot_owner"
# 45 days — long enough for return visits, short enough that abandoned
# anonymous buckets can be pruned by a background job.
COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 45


@dataclass(frozen=True, slots=True)
class Identity:
    owner_id: str
    conversation_id: str | None = None
    is_anonymous: bool = True


def generate_owner_id() -> str:
    """Return an opaque identifier that looks human-debuggable but
    cannot be guessed. Using UUID7 keeps IDs roughly time-sortable in
    logs; the entropy comes from ``uuid.uuid7()``."""
    try:
        return str(uuid.uuid7())
    except AttributeError:  # Python <3.11 fallback
        return str(uuid.uuid4())


def generate_conversation_id() -> str:
    try:
        return str(uuid.uuid7())
    except AttributeError:
        return str(uuid.uuid4())


def _cookie_expiry_iso() -> str:
    exp = datetime.now(UTC) + timedelta(seconds=COOKIE_MAX_AGE_SECONDS)
    return exp.strftime("%a, %d %b %Y %H:%M:%S GMT")


def read_or_create_identity(
    response: Response,
    cookie_value: str | None,
    *,
    secret: str,
    secure_cookie: bool = False,
    accept_unsigned: bool = False,
) -> Identity:
    """FastAPI dependency.

    If the cookie is missing or malformed, generate a fresh owner_id,
    set it as an HttpOnly+Secure+SameSite=Lax cookie, and return it.
    The returned Identity is what every downstream endpoint uses as
    ``owner_id``.

    ``secure_cookie`` is False by default so the cookie is also sent
    over plain HTTP during local development. Set it True in production
    behind HTTPS.
    """
    owner_id = _verify_cookie(cookie_value, secret)
    if owner_id is None and accept_unsigned and cookie_value and _looks_like_uuid(cookie_value):
        owner_id = cookie_value
    if owner_id is None:
        owner_id = generate_owner_id()

    response.set_cookie(
        key=COOKIE_NAME,
        value=_sign_cookie(owner_id, secret),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )
    return Identity(owner_id=owner_id)


def _sign_cookie(owner_id: str, secret: str) -> str:
    signature = hmac.new(secret.encode(), owner_id.encode(), hashlib.sha256).hexdigest()
    return f"{owner_id}.{signature}"


def _verify_cookie(value: str | None, secret: str) -> str | None:
    if not value or "." not in value:
        return None
    owner_id, signature = value.rsplit(".", 1)
    if not _looks_like_uuid(owner_id):
        return None
    expected = hmac.new(secret.encode(), owner_id.encode(), hashlib.sha256).hexdigest()
    return owner_id if hmac.compare_digest(signature, expected) else None


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
