from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from careerpilot.auth.models import Account, AuthSession, VerificationChallenge


class DuplicateAccountError(ValueError):
    def __init__(self, field: str) -> None:
        super().__init__(f"{field} already exists")
        self.field = field


class InvalidChallengeStateError(ValueError):
    pass


def normalize_identity(value: str) -> str:
    return value.strip().casefold()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SqliteAuthStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_normalized TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    email_normalized TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    verifier_hash TEXT NOT NULL,
                    remember_me INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    idle_expires_at TEXT NOT NULL,
                    absolute_expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS auth_sessions_account_idx
                    ON auth_sessions(account_id, revoked_at);
                CREATE TABLE IF NOT EXISTS email_verification_challenges (
                    id TEXT PRIMARY KEY,
                    email_normalized TEXT NOT NULL,
                    code_verifier TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_sent_at TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    consumed_at TEXT,
                    invalidated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS verification_email_idx
                    ON email_verification_challenges(email_normalized, created_at DESC);
                CREATE INDEX IF NOT EXISTS verification_source_idx
                    ON email_verification_challenges(source_key, created_at DESC);
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier_normalized TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    attempted_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS login_attempts_lookup_idx
                    ON login_attempts(identifier_normalized, source_key, attempted_at);
                """
            )

    def create_account(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        now: datetime,
        account_id: str | None = None,
        verification_challenge_id: str | None = None,
    ) -> Account:
        username_normalized = normalize_identity(username)
        email_normalized = normalize_identity(email)
        account_id = account_id or str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM accounts WHERE username_normalized = ?",
                (username_normalized,),
            ).fetchone():
                raise DuplicateAccountError("username")
            if connection.execute(
                "SELECT 1 FROM accounts WHERE email_normalized = ?", (email_normalized,)
            ).fetchone():
                raise DuplicateAccountError("email")
            if verification_challenge_id is not None:
                consumed = connection.execute(
                    """
                    UPDATE email_verification_challenges SET consumed_at = ?
                    WHERE id = ? AND consumed_at IS NULL AND invalidated_at IS NULL
                      AND expires_at > ?
                    """,
                    (_iso(now), verification_challenge_id, _iso(now)),
                )
                if consumed.rowcount != 1:
                    raise InvalidChallengeStateError("verification challenge is unavailable")
            try:
                connection.execute(
                    """
                    INSERT INTO accounts (
                        id, username, username_normalized, email, email_normalized,
                        password_hash, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (
                        account_id,
                        username.strip(),
                        username_normalized,
                        email.strip(),
                        email_normalized,
                        password_hash,
                        _iso(now),
                        _iso(now),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise DuplicateAccountError("username_or_email") from error
        account = self.get_account(account_id)
        assert account is not None
        return account

    def get_account(self, account_id: str) -> Account | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
        return self._account(row)

    def get_account_by_identifier(self, identifier: str) -> Account | None:
        normalized = normalize_identity(identifier)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM accounts
                   WHERE username_normalized = ? OR email_normalized = ?""",
                (normalized, normalized),
            ).fetchone()
        return self._account(row)

    def create_session(
        self,
        *,
        account_id: str,
        verifier_hash: str,
        remember_me: bool,
        created_at: datetime,
        idle_expires_at: datetime,
        absolute_expires_at: datetime,
    ) -> AuthSession:
        session_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    id, account_id, verifier_hash, remember_me, created_at, last_seen_at,
                    idle_expires_at, absolute_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    account_id,
                    verifier_hash,
                    int(remember_me),
                    _iso(created_at),
                    _iso(created_at),
                    _iso(idle_expires_at),
                    _iso(absolute_expires_at),
                ),
            )
        session = self.get_session(session_id)
        assert session is not None
        return session

    def get_session(self, session_id: str) -> AuthSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM auth_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._session(row)

    def revoke_session(self, session_id: str, revoked_at: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (_iso(revoked_at), session_id),
            )

    def touch_session(
        self, session_id: str, *, last_seen_at: datetime, idle_expires_at: datetime
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE auth_sessions SET last_seen_at = ?, idle_expires_at = ?
                   WHERE id = ? AND revoked_at IS NULL""",
                (_iso(last_seen_at), _iso(idle_expires_at), session_id),
            )

    def update_last_login(self, account_id: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE accounts SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (_iso(now), _iso(now), account_id),
            )

    def count_recent_login_failures(
        self, *, identifier: str, source_key: str, since: datetime
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count FROM login_attempts
                WHERE attempted_at >= ?
                  AND (identifier_normalized = ? OR source_key = ?)
                """,
                (_iso(since), normalize_identity(identifier), source_key),
            ).fetchone()
        return int(row["count"])

    def record_login_failure(
        self, *, identifier: str, source_key: str, attempted_at: datetime
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO login_attempts (identifier_normalized, source_key, attempted_at)
                VALUES (?, ?, ?)
                """,
                (normalize_identity(identifier), source_key, _iso(attempted_at)),
            )

    def clear_login_failures(self, *, identifier: str, source_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM login_attempts
                WHERE identifier_normalized = ? OR source_key = ?
                """,
                (normalize_identity(identifier), source_key),
            )

    def create_challenge(
        self,
        *,
        email_normalized: str,
        code_verifier: str,
        source_key: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> VerificationChallenge:
        challenge_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE email_verification_challenges
                SET invalidated_at = ?
                WHERE email_normalized = ? AND consumed_at IS NULL AND invalidated_at IS NULL
                """,
                (_iso(created_at), email_normalized),
            )
            connection.execute(
                """
                INSERT INTO email_verification_challenges (
                    id, email_normalized, code_verifier, source_key, created_at,
                    expires_at, last_sent_at, attempt_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    challenge_id,
                    email_normalized,
                    code_verifier,
                    source_key,
                    _iso(created_at),
                    _iso(expires_at),
                    _iso(created_at),
                ),
            )
        challenge = self.get_challenge(challenge_id)
        assert challenge is not None
        return challenge

    def get_challenge(self, challenge_id: str) -> VerificationChallenge | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM email_verification_challenges WHERE id = ?", (challenge_id,)
            ).fetchone()
        return self._challenge(row)

    def get_latest_challenge(self, email: str) -> VerificationChallenge | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM email_verification_challenges
                WHERE email_normalized = ? ORDER BY created_at DESC LIMIT 1
                """,
                (normalize_identity(email),),
            ).fetchone()
        return self._challenge(row)

    def get_active_challenge(
        self, email: str, now: datetime
    ) -> VerificationChallenge | None:
        challenge = self.get_latest_challenge(email)
        if (
            challenge is None
            or challenge.expires_at <= now
            or challenge.consumed_at is not None
            or challenge.invalidated_at is not None
        ):
            return None
        return challenge

    def count_recent_challenges(
        self,
        email_normalized: str | None,
        source_key: str | None,
        since: datetime,
    ) -> int:
        clauses = ["created_at >= ?"]
        values: list[str] = [_iso(since)]
        if email_normalized is not None:
            clauses.append("email_normalized = ?")
            values.append(normalize_identity(email_normalized))
        if source_key is not None:
            clauses.append("source_key = ?")
            values.append(source_key)
        with self._connect() as connection:
            query = (
                "SELECT COUNT(*) AS count FROM email_verification_challenges WHERE "
                + " AND ".join(clauses)
            )
            row = connection.execute(
                query,
                values,
            ).fetchone()
        return int(row["count"])

    def invalidate_challenge(self, challenge_id: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE email_verification_challenges SET invalidated_at = ?
                   WHERE id = ? AND consumed_at IS NULL AND invalidated_at IS NULL""",
                (_iso(now), challenge_id),
            )

    def record_failed_challenge_attempt(
        self, challenge_id: str, now: datetime, *, maximum: int
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE email_verification_challenges
                SET attempt_count = attempt_count + 1,
                    invalidated_at = CASE WHEN attempt_count + 1 >= ? THEN ? ELSE invalidated_at END
                WHERE id = ? AND consumed_at IS NULL AND invalidated_at IS NULL
                """,
                (maximum, _iso(now), challenge_id),
            )

    def consume_challenge(self, challenge_id: str, now: datetime) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE email_verification_challenges SET consumed_at = ?
                WHERE id = ? AND consumed_at IS NULL AND invalidated_at IS NULL
                  AND expires_at > ?
                """,
                (_iso(now), challenge_id, _iso(now)),
            )
        return cursor.rowcount == 1

    @staticmethod
    def _account(row: sqlite3.Row | None) -> Account | None:
        if row is None:
            return None
        return Account(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            status=row["status"],
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
            last_login_at=_datetime(row["last_login_at"]),
        )

    @staticmethod
    def _session(row: sqlite3.Row | None) -> AuthSession | None:
        if row is None:
            return None
        return AuthSession(
            id=row["id"],
            account_id=row["account_id"],
            verifier_hash=row["verifier_hash"],
            remember_me=bool(row["remember_me"]),
            created_at=_datetime(row["created_at"]),
            last_seen_at=_datetime(row["last_seen_at"]),
            idle_expires_at=_datetime(row["idle_expires_at"]),
            absolute_expires_at=_datetime(row["absolute_expires_at"]),
            revoked_at=_datetime(row["revoked_at"]),
        )

    @staticmethod
    def _challenge(row: sqlite3.Row | None) -> VerificationChallenge | None:
        if row is None:
            return None
        return VerificationChallenge(
            id=row["id"],
            email_normalized=row["email_normalized"],
            code_verifier=row["code_verifier"],
            source_key=row["source_key"],
            created_at=_datetime(row["created_at"]),
            expires_at=_datetime(row["expires_at"]),
            last_sent_at=_datetime(row["last_sent_at"]),
            attempt_count=int(row["attempt_count"]),
            consumed_at=_datetime(row["consumed_at"]),
            invalidated_at=_datetime(row["invalidated_at"]),
        )
