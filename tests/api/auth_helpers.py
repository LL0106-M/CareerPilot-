from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from careerpilot.auth.passwords import PasswordHasher
from careerpilot.auth.service import AuthService
from careerpilot.auth.store import SqliteAuthStore
from careerpilot.auth.verification import VerificationService


class NoopMailer:
    def send_registration_code(self, recipient: str, code: str) -> None:
        pass


def build_auth_service(path: Path) -> AuthService:
    store = SqliteAuthStore(path)
    verification = VerificationService(
        store=store,
        mailer=NoopMailer(),
        secret="test-verification-secret-at-least-32-bytes",
        code_factory=lambda: "123456",
    )
    return AuthService(
        store=store,
        password_hasher=PasswordHasher(),
        verification=verification,
    )


def issue_session(
    auth: AuthService,
    *,
    owner_id: str,
    username: str | None = None,
    email: str | None = None,
) -> dict[str, str]:
    existing = auth.store.get_account(owner_id)
    if existing is None:
        suffix = owner_id[-8:]
        auth.store.create_account(
            account_id=owner_id,
            username=username or f"user-{suffix}",
            email=email or f"user-{suffix}@example.com",
            password_hash="unused-in-route-tests",
            now=datetime.now(UTC),
        )
    verifier = f"test-verifier-{owner_id}-with-enough-entropy"
    now = datetime.now(UTC)
    session = auth.store.create_session(
        account_id=owner_id,
        verifier_hash=hashlib.sha256(verifier.encode()).hexdigest(),
        remember_me=True,
        created_at=now,
        idle_expires_at=now + timedelta(days=5),
        absolute_expires_at=now + timedelta(days=30),
    )
    return {"careerpilot_session": f"{session.id}.{verifier}"}
