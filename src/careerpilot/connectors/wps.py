"""WPS 365 file-creation adapter."""

import json
from collections.abc import Callable
from uuid import uuid4

import httpx

from careerpilot.actions.service import ConnectorOutcome


class WpsConnector:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        access_token: str,
        drive_id: str,
        parent_id: str,
        file_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._client = client
        self._access_token = access_token
        self._drive_id = drive_id
        self._parent_id = parent_id
        self._file_id_factory = file_id_factory or (lambda: str(uuid4()))

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
        response = await self._client.post(
            f"/v7/drives/{self._drive_id}/files/{self._parent_id}/create",
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            content=json.dumps(request_body, separators=(",", ":")),
        )
        if response.is_error:
            try:
                message = response.json().get("message", "WPS request failed")
            except ValueError:
                message = "WPS request failed"
            raise RuntimeError(str(message))
        data = response.json().get("data", {})
        file_data = data.get("file", data)
        reference = file_data.get("id") or file_data.get("file_id")
        if not reference:
            raise RuntimeError("WPS returned no file reference")
        observations = tuple(value for value in (file_data.get("url"),) if value)
        return ConnectorOutcome(external_reference=reference, observations=observations)

    async def verify(self, outcome: ConnectorOutcome) -> bool:
        return bool(outcome.external_reference)
