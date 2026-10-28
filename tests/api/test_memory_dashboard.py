from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.ideas import IdeaService, StorageAuthorization
from careerpilot.memory.models import (
    MemoryOrigin,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore
from careerpilot.product_store import ProductStore
from tests.api.auth_helpers import build_auth_service, issue_session


def test_dashboard_uses_canonical_memory_and_ignores_demo_memory_seed(tmp_path) -> None:
    unified = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memories = MemoryService(unified)
    ideas = IdeaService(memories)
    cognitive = SqliteCognitiveStore(tmp_path / "memory.db")
    products = ProductStore(tmp_path / "product.db")
    owner = "550e8400-e29b-41d4-a716-446655440000"
    memories.create_explicit(
        owner_id=owner, memory_type=MemoryType.GOAL, content="完成 AI 产品岗位准备"
    )
    memories.propose(
        owner_id=owner,
        memory_type=MemoryType.HYPOTHESIS,
        content="用户可能更适合小团队",
        origin=MemoryOrigin.DREAMING,
        source_type=MemorySourceType.DREAMING,
    )
    ideas.capture_explicit(
        owner_id=owner,
        raw_text="做一个面试复盘工具",
        title="面试复盘工具",
        authorization=StorageAuthorization.GRANTED,
    )
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(
        create_app(
            memory_service=memories,
            idea_service=ideas,
            cognitive_store=cognitive,
            product_store=products,
            auth_service=auth,
        )
    )
    try:
        dashboard = client.get(
            "/v1/me/dashboard", cookies=issue_session(auth, owner_id=owner)
        ).json()

        assert {item["content"] for item in dashboard["memories"]} == {
            "完成 AI 产品岗位准备",
            "做一个面试复盘工具",
        }
        assert dashboard["hypotheses"][0]["content"] == "用户可能更适合小团队"
        assert dashboard["ideas"][0]["title"] == "面试复盘工具"
        assert dashboard["ideas"][0]["raw_text"] == "做一个面试复盘工具"
        assert all(item["id"] != "mem-001" for item in dashboard["memories"])
        assert dashboard["journey"] == []
    finally:
        cognitive.close()
        products.close()
        unified.close()


def test_canonical_hypothesis_can_be_confirmed_and_added_to_journey(tmp_path) -> None:
    unified = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memories = MemoryService(unified)
    products = ProductStore(tmp_path / "product.db")
    owner = "550e8400-e29b-41d4-a716-446655440000"
    hypothesis = memories.propose(
        owner_id=owner,
        memory_type=MemoryType.HYPOTHESIS,
        content="我可能适合需要跨团队协作的产品岗位",
        origin=MemoryOrigin.DREAMING,
        source_type=MemorySourceType.DREAMING,
    )
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(
        create_app(
            memory_service=memories,
            product_store=products,
            auth_service=auth,
        )
    )
    client.cookies.update(issue_session(auth, owner_id=owner))
    try:
        confirmed = client.post(
            f"/v1/me/hypotheses/{hypothesis.id}/decision",
            json={"decision": "confirm"},
        )
        task = client.post(f"/v1/me/hypotheses/{hypothesis.id}/verification-task")

        assert confirmed.status_code == 200
        assert memories.get(owner, hypothesis.id).status is MemoryStatus.ACTIVE
        assert task.status_code == 200
        assert task.json()["related"] == hypothesis.content
        assert client.get("/v1/me/dashboard").json()["journey"][0]["hypothesis_id"] == hypothesis.id
    finally:
        products.close()
        unified.close()


def test_chat_idea_memory_appears_in_compass_and_can_create_a_journey_task(tmp_path) -> None:
    unified = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memories = MemoryService(unified)
    products = ProductStore(tmp_path / "product.db")
    owner = "550e8400-e29b-41d4-a716-446655440000"
    idea = memories.create_explicit(
        owner_id=owner,
        memory_type=MemoryType.IDEA,
        content="做一个帮助应届生复盘面试的工具",
        source_type=MemorySourceType.CONVERSATION,
        source_reference="run-1",
    )
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(
        create_app(
            memory_service=memories,
            product_store=products,
            auth_service=auth,
        )
    )
    client.cookies.update(issue_session(auth, owner_id=owner))
    try:
        dashboard = client.get("/v1/me/dashboard").json()
        task = client.post(f"/v1/me/ideas/{idea.id}/verification-task")

        assert dashboard["ideas"] == [
            {
                "id": idea.id,
                "memory_id": idea.id,
                "title": idea.content,
                "raw_text": idea.content,
                "stage": "captured",
                "created_at": idea.created_at.isoformat(),
            }
        ]
        assert task.status_code == 200
        assert task.json()["related"] == idea.content
        assert client.get("/v1/me/dashboard").json()["journey"][0]["idea_id"] == idea.id
    finally:
        products.close()
        unified.close()
