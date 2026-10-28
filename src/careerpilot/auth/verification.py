from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from careerpilot.auth.mailer import VerificationMailer
from careerpilot.auth.store import SqliteAuthStore, normalize_identity


class VerificationRateLimitError(ValueError):
    pass


class InvalidVerificationCodeError(ValueError):
    pass


class VerificationDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerificationDispatch:
    expires_at: datetime
    retry_after_seconds: int = 60


class VerificationService:
    def __init__(
        self,
        *,
        store: SqliteAuthStore,
        mailer: VerificationMailer,
        secret: str,
        code_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._mailer = mailer
        self._secret = secret.encode()
        self._code_factory = code_factory or (lambda: f"{secrets.randbelow(1_000_000):06d}")

    def request_registration_code(
        self, email: str, source_key: str, now: datetime
    ) -> VerificationDispatch:
        normalized = normalize_identity(email)
        latest = self._store.get_latest_challenge(normalized)
        if latest is not None and now - latest.last_sent_at < timedelta(seconds=60):
            raise VerificationRateLimitError("please wait before requesting another code")
        since = now - timedelta(hours=1)
        if self._store.count_recent_challenges(normalized, None, since) >= 5:
            raise VerificationRateLimitError("email verification limit reached")
        if self._store.count_recent_challenges(None, source_key, since) >= 5:
            raise VerificationRateLimitError("source verification limit reached")

        code = self._code_factory()
        if len(code) != 6 or not code.isdigit():
            raise ValueError("verification code factory must return six digits")
        expires_at = now + timedelta(minutes=10)
        challenge = self._store.create_challenge(
            email_normalized=normalized,
            code_verifier=self._verifier(normalized, code),
            source_key=source_key,
            created_at=now,
            expires_at=expires_at,
        )
        try:
            self._mailer.send_registration_code(email.strip(), code)
        except Exception as error:
            self._store.invalidate_challenge(challenge.id, now)
            raise VerificationDeliveryError("verification email could not be sent") from error
        return VerificationDispatch(expires_at=expires_at)

    def verify_registration_code(self, email: str, code: str, now: datetime) -> str:
        normalized = normalize_identity(email)
        challenge = self._store.get_latest_challenge(normalized)
        if (
            challenge is None
            or challenge.consumed_at is not None
            or challenge.invalidated_at is not None
            or challenge.expires_at <= now
            or challenge.attempt_count >= 5
        ):
            raise InvalidVerificationCodeError("verification code is invalid or expired")
        verifier = self._verifier(normalized, code)
        if not hmac.compare_digest(challenge.code_verifier, verifier):
            self._store.record_failed_challenge_attempt(challenge.id, now, maximum=5)
            raise InvalidVerificationCodeError("verification code is invalid or expired")
        return challenge.id

    def consume_registration_code(self, email: str, code: str, now: datetime) -> None:
        challenge_id = self.verify_registration_code(email, code, now)
        if not self._store.consume_challenge(challenge_id, now):
            raise InvalidVerificationCodeError("verification code is invalid or expired")

    def _verifier(self, email_normalized: str, code: str) -> str:
        return hmac.new(
            self._secret, f"{email_normalized}:{code}".encode(), hashlib.sha256
        ).hexdigest()
