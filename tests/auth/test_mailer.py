from email import policy
from email.parser import BytesParser

from careerpilot.auth.mailer import SmtpVerificationMailer


def test_verification_email_is_multipart_branded_and_contains_no_credentials() -> None:
    mailer = SmtpVerificationMailer(
        host="smtp.163.com",
        port=465,
        account="sender@163.com",
        authorization_code="smtp-secret",
        sender_name="CareerPilot 泊泊",
    )

    raw = mailer.build_message("person@example.com", "123456").as_bytes()
    message = BytesParser(policy=policy.default).parsebytes(raw)
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()

    assert message["Subject"] == "【CareerPilot】你的注册验证码"
    assert "CareerPilot 泊泊" in message["From"]
    assert message["To"] == "person@example.com"
    assert "123 456" in plain
    assert "123 456" in html
    assert "10 分钟" in plain
    assert "smtp-secret" not in raw.decode(errors="ignore")
