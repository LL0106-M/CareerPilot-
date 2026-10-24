from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore


def build_client(tmp_path):
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    service = MemoryService(store)
    return TestClient(create_app(memory_service=service)), store


def test_memory_api_derives_owner_and_enforces_lifecycle(tmp_path) -> None:
    client, store = build_client(tmp_path)
    owner_a = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
    owner_b = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440001"}
    try:
        created = client.post(
            "/v1/me/memories",
            cookies=owner_a,
            json={"type": "goal", "content": "本周完成三次投递", "importance": 5},
        )
        assert created.status_code == 201
        memory = created.json()
        assert memory["status"] == "active"
        assert memory["origin"] == "user_explicit"

        assert client.get("/v1/me/memories", cookies=owner_b).json()["items"] == []
        paused = client.post(
            f"/v1/me/memories/{memory['id']}/pause",
            cookies=owner_a,
            json={"expected_version": memory["version"]},
        )
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"
        stale = client.patch(
            f"/v1/me/memories/{memory['id']}",
            cookies=owner_a,
            json={"expected_version": 1, "content": "过期更新"},
        )
        assert stale.status_code == 409
    finally:
        store.close()


def test_memory_api_sensitive_create_is_candidate_and_confirmable(tmp_path) -> None:
    client, store = build_client(tmp_path)
    cookies = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
    try:
        created = client.post(
            "/v1/me/memories",
            cookies=cookies,
            json={
                "type": "fact",
                "content": "敏感健康信息",
                "sensitivity": "sensitive",
            },
        ).json()
        assert created["status"] == "candidate"
        confirmed = client.post(
            f"/v1/me/memories/{created['id']}/confirm",
            cookies=cookies,
            json={"expected_version": created["version"]},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "active"
    finally:
        store.close()
