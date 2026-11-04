import pytest

from careerpilot.harness.context import CareerContextCompiler, ContextRequest
from careerpilot.harness.memory import MemoryLifecycle
from careerpilot.memory.base import DisabledMemoryStore, MemoryContext, MemoryStoreError
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore
from careerpilot.support.policy import SupportPolicy


class RecordingCloudStore:
    enabled = True

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.turns: list[tuple[str, str, str, str]] = []

    async def search(self, user_id, conversation_id, query, mode=None):
        return MemoryContext()

    async def add_turn(
        self, user_id: str, conversation_id: str, user_message: str, assistant_message: str
    ) -> None:
        if self.fail:
            raise MemoryStoreError("cloud unavailable")
        self.turns.append((user_id, conversation_id, user_message, assistant_message))


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
    assert memories.get("u1", committed.memory_ids[0]).last_used_at is None


@pytest.mark.asyncio
async def test_multiple_candidates_roll_back_together_when_one_write_fails(
    tmp_path, monkeypatch
) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memories = MemoryService(store)
    lifecycle = MemoryLifecycle(DisabledMemoryStore(), unified_memory_service=memories)
    original = memories.remember_from_conversation
    calls = 0

    def fail_second(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("second candidate failed")
        return original(**kwargs)

    monkeypatch.setattr(memories, "remember_from_conversation", fail_second)

    committed = await lifecycle.commit_turn(
        user_id="u1",
        conversation_id="c1",
        user_message="记住：我的专业是计算机。记住：我的职业目标是产品经理",
        assistant_message="好的。",
        memories=MemoryContext(),
        turn_id="run-atomic",
    )

    assert committed.write_status == "unavailable"
    assert memories.list("u1") == ()


@pytest.mark.asyncio
async def test_canonical_write_is_followed_by_memos_dual_write(tmp_path) -> None:
    local = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))
    cloud = RecordingCloudStore()
    lifecycle = MemoryLifecycle(cloud, unified_memory_service=local)

    committed = await lifecycle.commit_turn(
        user_id="u1",
        conversation_id="c1",
        user_message="记住：我的长期目标是成为产品经理",
        assistant_message="好的，我会在后续规划中记住这个目标。",
        memories=MemoryContext(),
        turn_id="run-1",
    )

    assert committed.write_status == "accepted"
    assert committed.provider_write_status == "synced"
    assert cloud.turns == [
        (
            "u1",
            "c1",
            "记住：我的长期目标是成为产品经理",
            "好的，我会在后续规划中记住这个目标。",
        )
    ]


@pytest.mark.asyncio
async def test_memos_failure_does_not_rollback_canonical_memory(tmp_path) -> None:
    local = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))
    lifecycle = MemoryLifecycle(RecordingCloudStore(fail=True), unified_memory_service=local)

    committed = await lifecycle.commit_turn(
        user_id="u1",
        conversation_id="c1",
        user_message="记住：我的长期目标是成为产品经理",
        assistant_message="好的。",
        memories=MemoryContext(),
        turn_id="run-1",
    )

    assert committed.write_status == "accepted"
    assert committed.provider_write_status == "unavailable"
    assert [item.content for item in local.list("u1")] == ["我的长期目标是成为产品经理"]
