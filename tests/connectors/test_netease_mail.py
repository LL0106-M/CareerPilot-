import hashlib
import json

import pytest

from careerpilot.connectors.netease_mail import NeteaseMailConnector


class FakeImap:
    def __init__(self) -> None:
        self.calls = []
        self.logged_out = False

    def login(self, account, authorization_code):
        self.calls.append(("login", account, authorization_code))
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=False):
        self.calls.append(("select", mailbox, readonly))
        return "OK", [b"2"]

    def search(self, charset, *criteria):
        self.calls.append(("search", charset, criteria))
        return "OK", [b"1 2"]

    def fetch(self, message_id, query):
        self.calls.append(("fetch", message_id, query))
        headers = {
            b"2": (
                b"Subject: Interview invitation\r\n"
                b"From: recruiter@example.com\r\n"
                b"Date: Thu, 22 Oct 2026 10:00:00 +0800\r\n"
                b"Message-ID: <message-2@example.com>\r\n\r\n"
            ),
            b"1": (
                b"Subject: Your shopping receipt\r\n"
                b"From: store@example.com\r\n"
                b"Date: Wed, 21 Oct 2026 10:00:00 +0800\r\n"
                b"Message-ID: <message-1@example.com>\r\n\r\n"
            ),
        }
        return "OK", [(b"metadata", headers[message_id])]

    def logout(self):
        self.logged_out = True
        return "BYE", [b"logout"]


@pytest.mark.asyncio
async def test_netease_search_is_read_only_bounded_and_metadata_only() -> None:
    session = FakeImap()
    factories = []

    def factory(host, port):
        factories.append((host, port))
        return session

    connector = NeteaseMailConnector(
        host="imap.163.com",
        port=993,
        account="person@163.com",
        authorization_code="mail-secret",
        imap_factory=factory,
    )

    outcome = await connector.execute(
        "email.search_recruiting",
        {"since": "2026-10-01", "limit": 1},
    )

    assert factories == [("imap.163.com", 993)]
    assert ("select", "INBOX", True) in session.calls
    assert any(call[0] == "search" and "SINCE" in call[2] for call in session.calls)
    fetch_calls = [call for call in session.calls if call[0] == "fetch"]
    assert len(fetch_calls) == 1
    assert fetch_calls[0][2] == "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])"
    assert session.logged_out is True

    metadata = json.loads(outcome.observations[0])
    assert metadata == {
        "date": "Thu, 22 Oct 2026 10:00:00 +0800",
        "from": "recruiter@example.com",
        "message_id_hash": hashlib.sha256(b"<message-2@example.com>").hexdigest(),
        "subject": "Interview invitation",
    }
    assert "mail-secret" not in repr(outcome)
    assert "body" not in metadata


@pytest.mark.asyncio
async def test_netease_rejects_unbounded_lookback() -> None:
    connector = NeteaseMailConnector(
        host="imap.163.com",
        port=993,
        account="person@163.com",
        authorization_code="mail-secret",
        imap_factory=lambda host, port: FakeImap(),
    )

    with pytest.raises(ValueError, match="90 days"):
        await connector.execute("email.search_recruiting", {"since": "2020-01-01", "limit": 1})


@pytest.mark.asyncio
async def test_netease_probe_authenticates_read_only_and_logs_out() -> None:
    session = FakeImap()
    connector = NeteaseMailConnector(
        host="imap.163.com",
        port=993,
        account="person@163.com",
        authorization_code="mail-secret",
        imap_factory=lambda host, port: session,
    )

    assert await connector.probe() is True
    assert ("select", "INBOX", True) in session.calls
    assert session.logged_out is True
