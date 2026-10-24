from careerpilot.memory.models import (
    MemoryOrigin,
    MemorySensitivity,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)
from careerpilot.memory.service import MemoryQueryPurpose, MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore


def service(tmp_path) -> MemoryService:
    return MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))


def test_explicit_normal_memory_is_active_but_sensitive_memory_is_candidate(tmp_path) -> None:
    memories = service(tmp_path)

    normal = memories.create_explicit(
        owner_id="u1", memory_type=MemoryType.GOAL, content="本周完成三次投递"
    )
    sensitive = memories.create_explicit(
        owner_id="u1",
        memory_type=MemoryType.FACT,
        content="我的身份证号是 123456",
        sensitivity=MemorySensitivity.SENSITIVE,
    )

    assert normal.status is MemoryStatus.ACTIVE
    assert sensitive.status is MemoryStatus.CANDIDATE


def test_agent_proposal_stays_candidate_and_exact_duplicate_adds_evidence(tmp_path) -> None:
    memories = service(tmp_path)

    first = memories.propose(
        owner_id="u1",
        memory_type=MemoryType.PREFERENCE,
        content="偏好安静的工作环境",
        origin=MemoryOrigin.AGENT_EXTRACTED,
        source_type=MemorySourceType.CONVERSATION,
        source_reference="turn-1",
    )
    duplicate = memories.propose(
        owner_id="u1",
        memory_type=MemoryType.PREFERENCE,
        content="  偏好安静的工作环境  ",
        origin=MemoryOrigin.AGENT_EXTRACTED,
        source_type=MemorySourceType.CONVERSATION,
        source_reference="turn-2",
    )

    assert first.status is MemoryStatus.CANDIDATE
    assert duplicate.id == first.id
    assert len(memories.store.list_evidence("u1", first.id)) == 2


def test_contradiction_creates_candidate_relation_without_overwriting_active(tmp_path) -> None:
    memories = service(tmp_path)
    active = memories.create_explicit(
        owner_id="u1", memory_type=MemoryType.PREFERENCE, content="更喜欢稳定的大组织"
    )

    candidate = memories.propose(
        owner_id="u1",
        memory_type=MemoryType.PREFERENCE,
        content="现在更喜欢小团队",
        origin=MemoryOrigin.AGENT_EXTRACTED,
        source_type=MemorySourceType.CONVERSATION,
        contradicts_memory_id=active.id,
    )

    assert candidate.status is MemoryStatus.CANDIDATE
    assert memories.get("u1", active.id).content == "更喜欢稳定的大组织"
    assert memories.store.list_relations("u1", candidate.id) == (
        (candidate.id, active.id, "contradicts"),
    )


def test_search_returns_only_eligible_active_memory_and_respects_sensitive_intent(tmp_path) -> None:
    memories = service(tmp_path)
    ordinary = memories.create_explicit(
        owner_id="u1",
        memory_type=MemoryType.GOAL,
        content="准备产品经理面试",
        importance=5,
    )
    sensitive = memories.create_explicit(
        owner_id="u1",
        memory_type=MemoryType.FACT,
        content="我的病史需要在面试安排时避开上午",
        sensitivity=MemorySensitivity.SENSITIVE,
    )
    memories.confirm("u1", sensitive.id, expected_version=sensitive.version)
    proposed = memories.propose(
        owner_id="u1",
        memory_type=MemoryType.GOAL,
        content="也许转向研发岗位",
        origin=MemoryOrigin.AGENT_EXTRACTED,
        source_type=MemorySourceType.CONVERSATION,
    )

    normal = memories.search_context(
        owner_id="u1", query="面试", purpose=MemoryQueryPurpose.PLANNING
    )
    explicit = memories.search_context(
        owner_id="u1",
        query="病史 面试",
        purpose=MemoryQueryPurpose.PLANNING,
        explicit_personal_recall=True,
    )
    action = memories.search_context(
        owner_id="u1",
        query="病史",
        purpose=MemoryQueryPurpose.ACTION_PREVIEW,
        explicit_personal_recall=True,
    )

    assert [item.id for item in normal.records] == [ordinary.id]
    assert {item.id for item in explicit.records} == {ordinary.id, sensitive.id}
    assert sensitive.id not in {item.id for item in action.records}
    assert proposed.id not in {item.id for item in explicit.records}
