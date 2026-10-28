from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    username: str
    email: str
    password_hash: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuthSession:
    id: str
    account_id: str
    verifier_hash: str
    remember_me: bool
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VerificationChallenge:
    id: str
    email_normalized: str
    code_verifier: str
    source_key: str
    created_at: datetime
    expires_at: datetime
    last_sent_at: datetime
    attempt_count: int
    consumed_at: datetime | None = None
    invalidated_at: datetime | None = None
