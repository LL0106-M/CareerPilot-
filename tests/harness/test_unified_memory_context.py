import pytest

from careerpilot.harness.context import CareerContextCompiler, ContextRequest
from careerpilot.memory.models import MemoryOrigin, MemorySourceType, MemoryType
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore
from careerpilot.support.policy import SupportPolicy


class LegacyMemoryMustNotRun:
    async def search(self, *args, **kwargs):
        raise AssertionError("legacy memory search must not run when unified memory is configured")

    async def add_turn(self, *args, **kwargs):
        raise AssertionError("not used")


@pytest.mark.asyncio
async def test_context_compiler_uses_only_active_unified_memories(tmp_path) -> None:
    memories = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))
    active = memories.create_explicit(
        owner_id="u1", memory_type=MemoryType.GOAL, content="目标是进入 AI 产品岗位"
    )
    candidate = memories.propose(
        owner_id="u1",
        memory_type=MemoryType.GOAL,
        content="也许转向纯研发岗位",
        origin=MemoryOrigin.AGENT_EXTRACTED,
        source_type=MemorySourceType.CONVERSATION,
    )
    compiler = CareerContextCompiler(
        LegacyMemoryMustNotRun(),
        SupportPolicy(),
        unified_memory_service=memories,
    )

    context = await compiler.compile(
        ContextRequest(
            user_id="u1",
            conversation_id="c1",
            message="根据你记得的我的目标，帮我规划下一步",
        )
    )

    assert active.content in context.system_prompt
    assert candidate.content not in context.system_prompt
    assert context.memory_read_status == "available"
