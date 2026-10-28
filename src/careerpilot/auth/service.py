from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from careerpilot.auth.models import Account
from careerpilot.auth.passwords import PasswordHasher
from careerpilot.auth.store import (
    DuplicateAccountError,
    InvalidChallengeStateError,
    SqliteAuthStore,
)
from careerpilot.auth.verification import InvalidVerificationCodeError, VerificationService


class AuthenticationError(ValueError):
    pass


class LoginRateLimitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LoginResult:
    account: Account
    cookie_value: str
    remember_me: bool


class AuthService:
    def __init__(
        self,
        *,
        store: SqliteAuthStore,
        password_hasher: PasswordHasher,
        verification: VerificationService,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self._password_hasher = password_hasher
        self._verification = verification
        self._now = now_factory or (lambda: datetime.now(UTC))

    def request_registration_code(self, email: str, source_key: str):
        if self.store.get_account_by_identifier(email) is not None:
            raise DuplicateAccountError("email")
        return self._verification.request_registration_code(email, source_key, self._now())

    def register(self, *, username: str, email: str, password: str, code: str) -> Account:
        now = self._now()
        username_account = self.store.get_account_by_identifier(username)
        if username_account is not None:
            raise DuplicateAccountError("username")
        email_account = self.store.get_account_by_identifier(email)
        if email_account is not None:
            raise DuplicateAccountError("email")
        challenge_id = self._verification.verify_registration_code(email, code, now)
        try:
            return self.store.create_account(
                username=username,
                email=email,
                password_hash=self._password_hasher.hash(password),
                now=now,
                verification_challenge_id=challenge_id,
            )
        except InvalidChallengeStateError as error:
            raise InvalidVerificationCodeError(
                "verification code is invalid or expired"
            ) from error

    def login(
        self,
        *,
        identifier: str,
        password: str,
        remember_me: bool,
        source_key: str = "unknown",
    ) -> LoginResult:
        now = self._now()
        if self.store.count_recent_login_failures(
            identifier=identifier,
            source_key=source_key,
            since=now - timedelta(minutes=15),
        ) >= 5:
            raise LoginRateLimitError("too many login attempts")
        account = self.store.get_account_by_identifier(identifier)
        if (
            account is None
            or account.status != "active"
            or not self._password_hasher.verify(password, account.password_hash)
        ):
            self.store.record_login_failure(
                identifier=identifier, source_key=source_key, attempted_at=now
            )
            raise AuthenticationError("invalid credentials")
        self.store.clear_login_failures(identifier=identifier, source_key=source_key)
        verifier = secrets.token_urlsafe(32)
        verifier_hash = hashlib.sha256(verifier.encode()).hexdigest()
        absolute_expires_at = now + timedelta(days=30 if remember_me else 1)
        idle_expires_at = min(
            now + timedelta(days=5 if remember_me else 1), absolute_expires_at
        )
        session = self.store.create_session(
            account_id=account.id,
            verifier_hash=verifier_hash,
            remember_me=remember_me,
            created_at=now,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )
        self.store.update_last_login(account.id, now)
        return LoginResult(
            account=account, cookie_value=f"{session.id}.{verifier}", remember_me=remember_me
        )

    def authenticate(self, cookie_value: str | None) -> Account | None:
        parsed = self._parse_cookie(cookie_value)
        if parsed is None:
            return None
        session_id, verifier = parsed
        session = self.store.get_session(session_id)
        if session is None:
            return None
        supplied_hash = hashlib.sha256(verifier.encode()).hexdigest()
        if not hmac.compare_digest(session.verifier_hash, supplied_hash):
            return None
        now = self._now()
        if (
            session.revoked_at is not None
            or session.idle_expires_at <= now
            or session.absolute_expires_at <= now
        ):
            self.store.revoke_session(session.id, now)
            return None
        account = self.store.get_account(session.account_id)
        if account is None or account.status != "active":
            self.store.revoke_session(session.id, now)
            return None
        if session.remember_me and now - session.last_seen_at >= timedelta(hours=1):
            self.store.touch_session(
                session.id,
                last_seen_at=now,
                idle_expires_at=min(now + timedelta(days=5), session.absolute_expires_at),
            )
        return account

    def logout(self, cookie_value: str | None) -> None:
        parsed = self._parse_cookie(cookie_value)
        if parsed is not None:
            self.store.revoke_session(parsed[0], self._now())

    def is_remembered_session(self, cookie_value: str | None) -> bool:
        parsed = self._parse_cookie(cookie_value)
        if parsed is None:
            return False
        session = self.store.get_session(parsed[0])
        return session is not None and session.remember_me

    @staticmethod
    def _parse_cookie(cookie_value: str | None) -> tuple[str, str] | None:
        if not cookie_value or "." not in cookie_value:
            return None
        session_id, verifier = cookie_value.split(".", 1)
        if not session_id or len(verifier) < 32:
            return None
        return session_id, verifier
