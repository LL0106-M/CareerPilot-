from typing import Any

from fastapi.testclient import TestClient

from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.service import ActionService, ConnectorOutcome
from careerpilot.actions.store import SqliteActionStore
from careerpilot.api.app import create_app


class FakeConnector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def probe(self) -> bool:
        return True

    async def execute(self, capability: str, payload: dict[str, Any]) -> ConnectorOutcome:
        self.calls.append((capability, payload))
        return ConnectorOutcome("external-1", ("https://example.test/external-1",))

    async def verify(self, outcome: ConnectorOutcome) -> bool:
        return True


def build_client(tmp_path):
    store = SqliteActionStore(tmp_path / "actions.db")
    connector = FakeConnector()
    service = ActionService(
        registry=build_mvp_capability_registry(),
        store=store,
        connectors={"feishu": connector},
    )
    client = TestClient(create_app(action_store=store, action_service=service))
    return client, store, connector


def test_authorization_is_visible_revocable_and_owner_scoped(tmp_path) -> None:
    client, store, _ = build_client(tmp_path)
    try:
        owner_a = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
        owner_b = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440001"}
        granted = client.post(
            "/v1/me/integrations/feishu/grants",
            cookies=owner_a,
            json={
                "capabilities": ["document.create"],
                "purpose": "career_artifact_creation",
                "scope_snapshot": ["docs:write"],
            },
        )
        assert granted.status_code == 201
        grant_id = granted.json()["grant_id"]

        states_a = client.get("/v1/me/integrations", cookies=owner_a).json()["items"]
        states_b = client.get("/v1/me/integrations", cookies=owner_b).json()["items"]
        assert next(
            item
            for item in states_a
            if item["provider_id"] == "feishu" and item["capability"] == "document.create"
        )["grant_state"] == "granted"
        assert all("configured" in item and "connection_state" in item for item in states_a)
        assert next(
            item
            for item in states_b
            if item["provider_id"] == "feishu" and item["capability"] == "document.create"
        )["grant_state"] == "not_granted"

        forbidden = client.delete(
            f"/v1/me/integrations/feishu/grants/{grant_id}", cookies=owner_b
        )
        assert forbidden.status_code == 404
        revoked = client.delete(
            f"/v1/me/integrations/feishu/grants/{grant_id}", cookies=owner_a
        )
        assert revoked.status_code == 200
    finally:
        store.close()


def test_write_action_requires_preview_confirmation_and_is_idempotent(tmp_path) -> None:
    client, store, connector = build_client(tmp_path)
    try:
        cookies = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
        client.post(
            "/v1/me/integrations/feishu/grants",
            cookies=cookies,
            json={
                "capabilities": ["document.create"],
                "purpose": "career_artifact_creation",
            },
        )
        preview_response = client.post(
            "/v1/me/actions/preview",
            cookies=cookies,
            json={
                "provider_id": "feishu",
                "capability": "document.create",
                "payload": {"title": "Career Plan", "content": "# Plan"},
            },
        )
        assert preview_response.status_code == 201
        preview = preview_response.json()
        confirmation_response = client.post(
            f"/v1/me/actions/{preview['action_id']}/confirm",
            cookies=cookies,
            json={"preview_hash": preview["preview_hash"]},
        )
        assert confirmation_response.status_code == 201
        token = confirmation_response.json()["confirmation_token"]
        body = {
            "confirmation_token": token,
            "preview_hash": preview["preview_hash"],
            "idempotency_key": "request-1",
        }
        first = client.post(
            f"/v1/me/actions/{preview['action_id']}/apply", cookies=cookies, json=body
        )
        second = client.post(
            f"/v1/me/actions/{preview['action_id']}/apply", cookies=cookies, json=body
        )

        assert first.status_code == 200
        assert first.json() == second.json()
        assert first.json()["status"] == "completed"
        assert len(connector.calls) == 1
    finally:
        store.close()


def test_action_routes_reject_unknown_fields_and_map_missing_grant(tmp_path) -> None:
    client, store, _ = build_client(tmp_path)
    try:
        cookies = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
        missing_grant = client.post(
            "/v1/me/actions/preview",
            cookies=cookies,
            json={
                "provider_id": "feishu",
                "capability": "document.create",
                "payload": {"title": "Plan"},
            },
        )
        assert missing_grant.status_code == 403

        unknown_field = client.post(
            "/v1/me/integrations/feishu/grants",
            cookies=cookies,
            json={
                "capabilities": ["document.create"],
                "purpose": "career_artifact_creation",
                "access_token": "must-not-be-accepted",
            },
        )
        assert unknown_field.status_code == 422

        store.grant(
            owner_id="550e8400-e29b-41d4-a716-446655440000",
            provider_id="feishu",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
        )
        credential_payload = client.post(
            "/v1/me/actions/preview",
            cookies=cookies,
            json={
                "provider_id": "feishu",
                "capability": "document.create",
                "payload": {"title": "Plan", "access_token": "must-not-be-accepted"},
            },
        )
        assert credential_payload.status_code == 422
    finally:
        store.close()


def test_revoke_route_enforces_provider_scope(tmp_path) -> None:
    client, store, _ = build_client(tmp_path)
    try:
        cookies = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
        grant = store.grant(
            owner_id="550e8400-e29b-41d4-a716-446655440000",
            provider_id="wps",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
        )

        response = client.delete(
            f"/v1/me/integrations/feishu/grants/{grant.id}", cookies=cookies
        )

        assert response.status_code == 404
        assert store.find_active_grant(
            "550e8400-e29b-41d4-a716-446655440000", "wps", "document.create"
        ) is not None
    finally:
        store.close()
