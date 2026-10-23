"""WPS 365 file-creation adapter."""

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import format_datetime
from uuid import uuid4

import httpx

from careerpilot.actions.service import ConnectorError, ConnectorOutcome


class WpsConnector:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        access_token: str,
        drive_id: str,
        parent_id: str,
        file_id_factory: Callable[[], str] | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        date_factory: Callable[[], str] | None = None,
    ) -> None:
        self._client = client
        self._access_token = access_token
        self._drive_id = drive_id
        self._parent_id = parent_id
        self._file_id_factory = file_id_factory or (lambda: str(uuid4()))
        self._access_key = access_key
        self._secret_key = secret_key
        self._date_factory = date_factory or (
            lambda: format_datetime(datetime.now(UTC), usegmt=True)
        )
        if bool(access_key) != bool(secret_key):
            raise ValueError("WPS access_key and secret_key must be configured together")

    async def probe(self) -> bool:
        return bool(self._access_token and self._drive_id and self._parent_id)

    async def execute(self, capability: str, payload: dict) -> ConnectorOutcome:
        if capability != "document.create":
            raise ValueError(f"unsupported WPS capability: {capability}")
        request_body = {
            "file_id": self._file_id_factory(),
            "file_type": str(payload.get("file_type", "docx")),
            "name": str(payload["name"]),
            "on_name_conflict": "rename",
        }
        path = f"/v7/drives/{self._drive_id}/files/{self._parent_id}/create"
        body = json.dumps(request_body, separators=(",", ":"))
        try:
            response = await self._client.post(
                path,
                headers=self._headers("POST", path, body),
                content=body,
            )
        except httpx.TimeoutException as error:
            raise ConnectorError(
                "WPS request timed out", retryable=False, uncertain=True
            ) from error
        if response.is_error:
            try:
                message = response.json().get("message", "WPS request failed")
            except ValueError:
                message = "WPS request failed"
            raise ConnectorError(str(message), retryable=False)
        envelope = response.json()
        if envelope.get("code", 0) != 0:
            raise ConnectorError(str(envelope.get("msg", "WPS request failed")), retryable=False)
        file_data = envelope.get("data", {})
        reference = file_data.get("id")
        if not reference:
            raise ConnectorError("WPS returned no file reference", retryable=False)
        observations = tuple(value for value in (file_data.get("link_url"),) if value)
        return ConnectorOutcome(external_reference=reference, observations=observations)

    async def verify(self, outcome: ConnectorOutcome) -> bool:
        if not outcome.external_reference:
            return False
        path = f"/v7/files/{outcome.external_reference}/meta"
        try:
            response = await self._client.get(path, headers=self._headers("GET", path, ""))
        except httpx.HTTPError:
            return False
        if response.is_error:
            return False
        envelope = response.json()
        return envelope.get("code", 0) == 0 and envelope.get("data", {}).get(
            "id"
        ) == outcome.external_reference

    def _headers(self, method: str, path: str, body: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        if self._access_key and self._secret_key:
            kso_date = self._date_factory()
            body_hash = hashlib.sha256(body.encode()).hexdigest() if body else ""
            signable = f"KSO-1{method}{path}application/json{kso_date}{body_hash}"
            signature = hmac.new(
                self._secret_key.encode(), signable.encode(), hashlib.sha256
            ).hexdigest()
            headers["X-Kso-Date"] = kso_date
            headers["X-Kso-Authorization"] = f"KSO-1 {self._access_key}:{signature}"
        return headers
