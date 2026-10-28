from datetime import UTC, datetime, timedelta

import pytest

from careerpilot.auth.store import DuplicateAccountError, SqliteAuthStore

NOW = datetime(2026, 10, 27, 6, 0, tzinfo=UTC)


def test_account_identity_is_unique_and_case_insensitive(tmp_path) -> None:
    store = SqliteAuthStore(tmp_path / "auth.db")
    account = store.create_account(
        username="CareerDreamer",
        email="Pilot@Example.com",
        password_hash="$argon2id$stored",
        now=NOW,
    )

    assert store.get_account_by_identifier(" careerdreamer ") == account
    assert store.get_account_by_identifier("PILOT@example.COM") == account
    with pytest.raises(DuplicateAccountError) as username_error:
        store.create_account(
            username="careerdreamer",
            email="other@example.com",
            password_hash="$argon2id$other",
            now=NOW,
        )
    assert username_error.value.field == "username"
    with pytest.raises(DuplicateAccountError) as email_error:
        store.create_account(
            username="someone-else",
            email="pilot@example.com",
            password_hash="$argon2id$other",
            now=NOW,
        )
    assert email_error.value.field == "email"


def test_session_store_persists_only_verifier_hash_and_supports_revocation(tmp_path) -> None:
    store = SqliteAuthStore(tmp_path / "auth.db")
    account = store.create_account(
        username="pilot",
        email="pilot@example.com",
        password_hash="$argon2id$stored",
        now=NOW,
    )
    verifier_hash = "a" * 64
    session = store.create_session(
        account_id=account.id,
        verifier_hash=verifier_hash,
        remember_me=True,
        created_at=NOW,
        idle_expires_at=NOW + timedelta(days=5),
        absolute_expires_at=NOW + timedelta(days=30),
    )

    stored = store.get_session(session.id)
    assert stored is not None
    assert stored.verifier_hash == verifier_hash

    store.revoke_session(session.id, NOW + timedelta(minutes=2))

    assert store.get_session(session.id).revoked_at == NOW + timedelta(minutes=2)
