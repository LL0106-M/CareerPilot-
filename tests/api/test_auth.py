from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.auth.passwords import PasswordHasher
from careerpilot.auth.service import AuthService
from careerpilot.auth.store import SqliteAuthStore
from careerpilot.auth.verification import VerificationService
from careerpilot.config import Settings


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class RecordingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_registration_code(self, recipient: str, code: str) -> None:
        self.sent.append((recipient, code))


def auth_client(tmp_path) -> tuple[TestClient, MutableClock, RecordingMailer]:
    clock = MutableClock()
    mailer = RecordingMailer()
    store = SqliteAuthStore(tmp_path / "auth.db")
    verification = VerificationService(
        store=store,
        mailer=mailer,
        secret="verification-secret-at-least-32-bytes",
        code_factory=lambda: "123456",
    )
    auth = AuthService(
        store=store,
        password_hasher=PasswordHasher(),
        verification=verification,
        now_factory=clock,
    )
    settings = Settings(
        _env_file=None,
        CAREERPILOT_AUTH_DB_PATH=tmp_path / "auth.db",
        CAREERPILOT_RAG_DB_PATH=tmp_path / "rag.db",
        CAREERPILOT_MEMORY_DB_PATH=tmp_path / "memory.db",
        CAREERPILOT_SESSION_DB_PATH=tmp_path / "sessions.db",
        CAREERPILOT_PRODUCT_DB_PATH=tmp_path / "product.db",
        CAREERPILOT_ACTION_DB_PATH=tmp_path / "actions.db",
    )
    return TestClient(create_app(settings=settings, auth_service=auth)), clock, mailer


def register(client: TestClient) -> None:
    sent = client.post("/v1/auth/verification-codes", json={"email": "pilot@example.com"})
    assert sent.status_code == 202
    created = client.post(
        "/v1/auth/register",
        json={
            "username": "careerpilot",
            "email": "pilot@example.com",
            "verification_code": "123456",
            "password": "A secure passphrase 2026!",
        },
    )
    assert created.status_code == 201


def test_registration_verifies_email_and_does_not_log_user_in(tmp_path) -> None:
    client, _, mailer = auth_client(tmp_path)

    register(client)

    assert mailer.sent == [("pilot@example.com", "123456")]
    assert client.get("/v1/auth/me").status_code == 401


def test_login_accepts_username_or_email_and_returns_current_account(tmp_path) -> None:
    client, _, _ = auth_client(tmp_path)
    register(client)

    response = client.post(
        "/v1/auth/login",
        json={
            "identifier": "CAREERPILOT",
            "password": "A secure passphrase 2026!",
            "remember_me": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["username"] == "careerpilot"
    assert "careerpilot_session=" in response.headers["set-cookie"]
    assert "Max-Age" not in response.headers["set-cookie"]
    assert client.get("/v1/auth/me").json() == response.json()

    client.post("/v1/auth/logout")
    email_login = client.post(
        "/v1/auth/login",
        json={
            "identifier": "PILOT@EXAMPLE.COM",
            "password": "A secure passphrase 2026!",
            "remember_me": True,
        },
    )
    assert email_login.status_code == 200
    assert "Max-Age=432000" in email_login.headers["set-cookie"]


def test_login_failure_is_generic_and_logout_revokes_old_cookie(tmp_path) -> None:
    client, _, _ = auth_client(tmp_path)
    register(client)

    unknown = client.post(
        "/v1/auth/login",
        json={"identifier": "missing", "password": "wrong-password", "remember_me": False},
    )
    wrong = client.post(
        "/v1/auth/login",
        json={"identifier": "careerpilot", "password": "wrong-password", "remember_me": False},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "用户名、邮箱或密码不正确"}

    client.post(
        "/v1/auth/login",
        json={
            "identifier": "careerpilot",
            "password": "A secure passphrase 2026!",
            "remember_me": True,
        },
    )
    stolen_cookie = client.cookies.get("careerpilot_session")
    assert client.post("/v1/auth/logout").status_code == 200
    assert client.get(
        "/v1/auth/me", cookies={"careerpilot_session": stolen_cookie}
    ).status_code == 401


def test_remembered_session_expires_after_five_days_idle(tmp_path) -> None:
    client, clock, _ = auth_client(tmp_path)
    register(client)
    client.post(
        "/v1/auth/login",
        json={
            "identifier": "careerpilot",
            "password": "A secure passphrase 2026!",
            "remember_me": True,
        },
    )

    clock.now += timedelta(days=5, seconds=1)

    response = client.get("/v1/auth/me")
    assert response.status_code == 401
    assert "careerpilot_session=;" in response.headers["set-cookie"]


def test_active_remembered_session_refreshes_browser_cookie_window(tmp_path) -> None:
    client, clock, _ = auth_client(tmp_path)
    register(client)
    client.post(
        "/v1/auth/login",
        json={
            "identifier": "careerpilot",
            "password": "A secure passphrase 2026!",
            "remember_me": True,
        },
    )
    clock.now += timedelta(days=4)

    response = client.get("/v1/auth/me")

    assert response.status_code == 200
    assert "Max-Age=432000" in response.headers["set-cookie"]


def test_login_is_temporarily_limited_after_repeated_failures(tmp_path) -> None:
    client, _, _ = auth_client(tmp_path)
    register(client)
    body = {
        "identifier": "careerpilot",
        "password": "wrong-password",
        "remember_me": False,
    }

    for _ in range(5):
        assert client.post("/v1/auth/login", json=body).status_code == 401

    limited = client.post("/v1/auth/login", json=body)
    assert limited.status_code == 429
    assert limited.json() == {"detail": "登录尝试过多，请稍后再试"}


def test_cookie_authenticated_mutation_rejects_cross_site_origin(tmp_path) -> None:
    client, _, _ = auth_client(tmp_path)
    register(client)
    client.post(
        "/v1/auth/login",
        json={
            "identifier": "careerpilot",
            "password": "A secure passphrase 2026!",
            "remember_me": False,
        },
    )

    response = client.post(
        "/v1/auth/logout",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403


def test_cookie_authenticated_mutation_accepts_forwarded_same_origin(tmp_path) -> None:
    client, _, _ = auth_client(tmp_path)
    register(client)
    client.post(
        "/v1/auth/login",
        json={
            "identifier": "careerpilot",
            "password": "A secure passphrase 2026!",
            "remember_me": False,
        },
    )

    response = client.post(
        "/v1/auth/logout",
        headers={
            "Origin": "https://careerpilot.ngrok-free.dev",
            "X-Forwarded-Host": "careerpilot.ngrok-free.dev",
            "X-Forwarded-Proto": "https",
        },
    )

    assert response.status_code == 200
