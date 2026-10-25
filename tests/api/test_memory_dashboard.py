from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.ideas import IdeaService, StorageAuthorization
from careerpilot.memory.models import MemoryOrigin, MemorySourceType, MemoryType
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore
from careerpilot.product_store import ProductStore


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
    client = TestClient(
        create_app(
            memory_service=memories,
            idea_service=ideas,
            cognitive_store=cognitive,
            product_store=products,
        )
    )
    try:
        dashboard = client.get(
            "/v1/me/dashboard", cookies={"careerpilot_owner": owner}
        ).json()

        assert {item["content"] for item in dashboard["memories"]} == {
            "完成 AI 产品岗位准备",
            "做一个面试复盘工具",
        }
        assert dashboard["hypotheses"][0]["content"] == "用户可能更适合小团队"
        assert dashboard["ideas"][0]["title"] == "面试复盘工具"
        assert all(item["id"] != "mem-001" for item in dashboard["memories"])
    finally:
        cognitive.close()
        products.close()
        unified.close()
