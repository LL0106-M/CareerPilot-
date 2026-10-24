"""Read-only NetEase Mail recruiting metadata search over IMAP SSL."""

import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from email import policy
from email.parser import BytesParser
from imaplib import IMAP4_SSL
from typing import Any

from careerpilot.actions.service import ConnectorOutcome


class NeteaseMailConnector:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        account: str,
        authorization_code: str,
        imap_factory: Callable[[str, int], Any] = IMAP4_SSL,
    ) -> None:
        self._host = host
        self._port = port
        self._account = account
        self._authorization_code = authorization_code
        self._imap_factory = imap_factory

    async def probe(self) -> bool:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._probe_sync), timeout=10)
        except Exception:
            return False

    async def execute(self, capability: str, payload: dict) -> ConnectorOutcome:
        if capability != "email.search_recruiting":
            raise ValueError(f"unsupported NetEase Mail capability: {capability}")
        return await asyncio.to_thread(self._search, payload)

    async def verify(self, outcome: ConnectorOutcome) -> bool:
        return True

    def _probe_sync(self) -> bool:
        session = self._imap_factory(self._host, self._port)
        try:
            login_status, _ = session.login(self._account, self._authorization_code)
            select_status, _ = session.select("INBOX", readonly=True)
            return login_status == "OK" and select_status == "OK"
        finally:
            session.logout()

    def _search(self, payload: dict) -> ConnectorOutcome:
        since = self._imap_date(payload.get("since"))
        session = self._imap_factory(self._host, self._port)
        try:
            session.login(self._account, self._authorization_code)
            session.select("INBOX", readonly=True)
            status, results = session.search(None, "SINCE", since)
            if status != "OK":
                raise RuntimeError("NetEase Mail search failed")
            limit = max(1, min(int(payload.get("limit", 20)), 100))
            message_ids = results[0].split()[-limit:][::-1]
            keywords = tuple(
                keyword.casefold()
                for keyword in ("interview", "recruit", "offer", "面试", "招聘", "录用")
            )
            matches = []
            for message_id in message_ids:
                metadata = self._fetch_metadata(session, message_id)
                searchable = f"{metadata['subject']} {metadata['from']}".casefold()
                if any(keyword in searchable for keyword in keywords):
                    matches.append(metadata)
            observations = tuple(
                json.dumps(item, ensure_ascii=False, sort_keys=True) for item in matches
            )
            return ConnectorOutcome(
                external_reference=f"netease-search:{len(matches)}", observations=observations
            )
        finally:
            session.logout()

    @staticmethod
    def _imap_date(value: str | date | None) -> str:
        if value is None:
            parsed = date.today()
        elif isinstance(value, date):
            parsed = value
        else:
            parsed = datetime.fromisoformat(value).date()
        today = date.today()
        if parsed > today or parsed < today - timedelta(days=90):
            raise ValueError("since must be within the last 90 days")
        return parsed.strftime("%d-%b-%Y")

    @staticmethod
    def _fetch_metadata(session: Any, message_id: bytes) -> dict[str, str]:
        query = "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])"
        status, parts = session.fetch(message_id, query)
        if status != "OK":
            raise RuntimeError("NetEase Mail metadata fetch failed")
        raw_headers = next(part[1] for part in parts if isinstance(part, tuple))
        message = BytesParser(policy=policy.default).parsebytes(raw_headers, headersonly=True)
        return {
            "date": str(message.get("Date", "")),
            "from": str(message.get("From", "")),
            "message_id_hash": hashlib.sha256(
                str(message.get("Message-ID", "")).encode()
            ).hexdigest(),
            "subject": str(message.get("Subject", "")),
        }
