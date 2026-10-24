from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.memory.ideas import IdeaService
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore


def test_idea_api_returns_authorization_and_never_accepts_owner_from_body(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memories = MemoryService(store)
    ideas = IdeaService(memories)
    client = TestClient(create_app(memory_service=memories, idea_service=ideas))
    cookies = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
    try:
        rejected = client.post(
            "/v1/me/ideas",
            cookies=cookies,
            json={
                "raw_text": "做一个面试复盘工具",
                "title": "面试复盘工具",
                "authorization": "granted",
                "owner_id": "attacker",
            },
        )
        assert rejected.status_code == 422

        created = client.post(
            "/v1/me/ideas",
            cookies=cookies,
            json={
                "raw_text": "做一个面试复盘工具",
                "title": "面试复盘工具",
                "authorization": "granted",
            },
        )
        assert created.status_code == 201
        item = created.json()
        assert item["authorization"] == "granted"
        assert item["memory_status"] == "active"
        assert client.get("/v1/me/ideas", cookies=cookies).json()["items"][0]["id"] == item["id"]
    finally:
        store.close()


def test_idea_api_denied_authorization_does_not_persist(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memories = MemoryService(store)
    ideas = IdeaService(memories)
    client = TestClient(create_app(memory_service=memories, idea_service=ideas))
    cookies = {"careerpilot_owner": "550e8400-e29b-41d4-a716-446655440000"}
    try:
        response = client.post(
            "/v1/me/ideas",
            cookies=cookies,
            json={
                "raw_text": "不要保存这个想法",
                "title": "临时想法",
                "authorization": "denied",
            },
        )
        assert response.status_code == 403
        assert client.get("/v1/me/ideas", cookies=cookies).json()["items"] == []
    finally:
        store.close()
