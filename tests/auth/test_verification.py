from datetime import UTC, datetime, timedelta

import pytest

from careerpilot.auth.store import SqliteAuthStore
from careerpilot.auth.verification import (
    InvalidVerificationCodeError,
    VerificationDeliveryError,
    VerificationRateLimitError,
    VerificationService,
)

NOW = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)


class RecordingMailer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, str]] = []

    def send_registration_code(self, recipient: str, code: str) -> None:
        if self.fail:
            raise RuntimeError("smtp unavailable")
        self.sent.append((recipient, code))


def make_service(tmp_path, mailer=None) -> tuple[VerificationService, SqliteAuthStore]:
    store = SqliteAuthStore(tmp_path / "auth.db")
    return (
        VerificationService(
            store=store,
            mailer=mailer or RecordingMailer(),
            secret="verification-secret-at-least-32-bytes",
            code_factory=lambda: "123456",
        ),
        store,
    )


def test_request_sends_six_digit_code_with_ten_minute_expiry(tmp_path) -> None:
    mailer = RecordingMailer()
    service, _ = make_service(tmp_path, mailer)

    dispatch = service.request_registration_code(" Person@Example.com ", "source-a", NOW)

    assert mailer.sent == [("Person@Example.com", "123456")]
    assert dispatch.expires_at == NOW + timedelta(minutes=10)
    assert dispatch.retry_after_seconds == 60


def test_request_rejects_resend_before_sixty_seconds_and_sixth_hourly_send(tmp_path) -> None:
    service, _ = make_service(tmp_path)
    service.request_registration_code("person@example.com", "source-a", NOW)
    with pytest.raises(VerificationRateLimitError):
        service.request_registration_code(
            "person@example.com", "source-a", NOW + timedelta(seconds=59)
        )
    for index in range(1, 5):
        service.request_registration_code(
            "person@example.com", "source-a", NOW + timedelta(minutes=index)
        )
    with pytest.raises(VerificationRateLimitError):
        service.request_registration_code(
            "person@example.com", "source-a", NOW + timedelta(minutes=5)
        )


def test_latest_code_is_single_use_and_new_request_invalidates_previous_code(tmp_path) -> None:
    codes = iter(("111111", "222222"))
    store = SqliteAuthStore(tmp_path / "auth.db")
    service = VerificationService(
        store=store,
        mailer=RecordingMailer(),
        secret="verification-secret-at-least-32-bytes",
        code_factory=lambda: next(codes),
    )
    service.request_registration_code("person@example.com", "source-a", NOW)
    service.request_registration_code(
        "person@example.com", "source-a", NOW + timedelta(seconds=61)
    )

    with pytest.raises(InvalidVerificationCodeError):
        service.consume_registration_code(
            "person@example.com", "111111", NOW + timedelta(seconds=62)
        )
    service.consume_registration_code(
        "person@example.com", "222222", NOW + timedelta(seconds=62)
    )
    with pytest.raises(InvalidVerificationCodeError):
        service.consume_registration_code(
            "person@example.com", "222222", NOW + timedelta(seconds=63)
        )


def test_code_expires_and_locks_after_five_wrong_attempts(tmp_path) -> None:
    service, _ = make_service(tmp_path)
    service.request_registration_code("person@example.com", "source-a", NOW)
    for second in range(1, 6):
        with pytest.raises(InvalidVerificationCodeError):
            service.consume_registration_code(
                "person@example.com", "000000", NOW + timedelta(seconds=second)
            )
    with pytest.raises(InvalidVerificationCodeError):
        service.consume_registration_code(
            "person@example.com", "123456", NOW + timedelta(seconds=6)
        )

    service.request_registration_code(
        "other@example.com", "source-a", NOW + timedelta(minutes=6)
    )
    with pytest.raises(InvalidVerificationCodeError):
        service.consume_registration_code(
            "other@example.com", "123456", NOW + timedelta(minutes=17)
        )


def test_smtp_failure_invalidates_challenge_instead_of_claiming_delivery(tmp_path) -> None:
    service, store = make_service(tmp_path, RecordingMailer(fail=True))

    with pytest.raises(VerificationDeliveryError):
        service.request_registration_code("person@example.com", "source-a", NOW)

    assert store.get_active_challenge("person@example.com", NOW) is None
