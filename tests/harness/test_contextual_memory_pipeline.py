import pytest

from careerpilot.harness.context import CareerContextCompiler, ContextRequest
from careerpilot.harness.memory import MemoryLifecycle
from careerpilot.memory.base import DisabledMemoryStore, MemoryContext
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore
from careerpilot.support.policy import SupportPolicy


@pytest.mark.asyncio
async def test_turn_write_is_recalled_and_combined_with_rag_context(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memories = MemoryService(store)
    lifecycle = MemoryLifecycle(
        DisabledMemoryStore(),
        unified_memory_service=memories,
    )

    committed = await lifecycle.commit_turn(
        user_id="u1",
        conversation_id="c1",
        user_message="记住：以后我做职业选择时更看重稳定节奏",
        assistant_message="好的。",
        memories=MemoryContext(),
        turn_id="run-1",
    )
    compiler = CareerContextCompiler(
        DisabledMemoryStore(),
        SupportPolicy(),
        unified_memory_service=memories,
    )

    context = await compiler.compile(
        ContextRequest(
            user_id="u1",
            conversation_id="c1",
            message="根据你记得的我的偏好，帮我看看有哪些产品岗位",
        )
    )

    assert committed.write_status == "accepted"
    assert len(committed.memory_ids) == 1
    assert "更看重稳定节奏" in context.system_prompt
    assert "外部事实必须由 RAG 证据支持" in context.system_prompt
    assert "search_career_knowledge" in context.allowed_tool_names
    assert memories.get("u1", committed.memory_ids[0]).last_used_at is not None
