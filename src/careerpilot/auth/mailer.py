# ruff: noqa: E501
from __future__ import annotations

import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from typing import Protocol


class VerificationMailer(Protocol):
    def send_registration_code(self, recipient: str, code: str) -> None: ...


class SmtpVerificationMailer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        account: str,
        authorization_code: str,
        sender_name: str,
        smtp_factory=smtplib.SMTP_SSL,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._account = account
        self._authorization_code = authorization_code
        self._sender_name = sender_name
        self._smtp_factory = smtp_factory
        self._timeout_seconds = timeout_seconds

    def build_message(self, recipient: str, code: str) -> EmailMessage:
        grouped_code = f"{code[:3]} {code[3:]}"
        message = EmailMessage()
        local, _, domain = self._account.partition("@")
        message["Subject"] = "【CareerPilot】你的注册验证码"
        message["From"] = Address(self._sender_name, local, domain)
        message["To"] = recipient
        message.set_content(
            "\n".join(
                (
                    "CareerPilot · 泊泊",
                    "",
                    "验证你的邮箱",
                    "",
                    "你正在注册 CareerPilot。请输入下面的验证码完成注册：",
                    "",
                    f"    {grouped_code}",
                    "",
                    "验证码将在 10 分钟后失效。",
                    "如果这不是你的操作，可以安全忽略这封邮件。",
                    "",
                    "CareerPilot · 陪你慢慢找到方向",
                )
            )
        )
        message.add_alternative(
            f"""
            <!doctype html>
            <html lang="zh-CN">
              <body style="margin:0;background:#f5f1e8;color:#24332d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;">
                <div style="padding:48px 16px;">
                  <div style="max-width:600px;margin:0 auto;padding:40px;border:1px solid rgba(63,117,98,.14);border-radius:24px;background:#fffdf8;box-shadow:0 16px 48px rgba(36,51,45,.08);">
                    <div style="color:#3f7562;font-size:14px;font-weight:700;letter-spacing:.08em;">CareerPilot · 泊泊</div>
                    <h1 style="margin:28px 0 12px;font-family:Georgia,'Songti SC',serif;font-size:30px;font-weight:500;">验证你的邮箱</h1>
                    <p style="margin:0;color:#617069;font-size:15px;line-height:1.8;">你正在注册 CareerPilot。请输入下面的验证码完成注册：</p>
                    <div style="margin:30px 0;padding:22px;border-radius:18px;background:#e8f0ec;color:#315f50;font-size:36px;font-weight:700;letter-spacing:.18em;text-align:center;">{grouped_code}</div>
                    <p style="margin:0;color:#617069;font-size:14px;line-height:1.8;">验证码将在 <strong>10 分钟</strong>后失效。<br>如果这不是你的操作，可以安全忽略这封邮件。</p>
                    <div style="margin-top:32px;padding-top:20px;border-top:1px solid #ece8df;color:#8a9690;font-size:12px;">CareerPilot · 陪你慢慢找到方向</div>
                  </div>
                </div>
              </body>
            </html>
            """,
            subtype="html",
        )
        return message

    def send_registration_code(self, recipient: str, code: str) -> None:
        message = self.build_message(recipient, code)
        with self._smtp_factory(
            self._host, self._port, timeout=self._timeout_seconds
        ) as session:
            session.login(self._account, self._authorization_code)
            session.send_message(message)
