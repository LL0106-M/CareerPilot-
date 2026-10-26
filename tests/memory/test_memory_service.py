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


class SemanticEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        del text
        return [1.0, 0.0]


def test_search_combines_semantic_recall_with_memory_governance(tmp_path) -> None:
    memories = MemoryService(
        SqliteUnifiedMemoryStore(tmp_path / "memory.db"),
        embedder=SemanticEmbedder(),
    )
    stored = memories.create_explicit(
        owner_id="u1",
        memory_type=MemoryType.PREFERENCE,
        content="偏好安静且边界清晰的团队",
    )

    result = memories.search_context(
        owner_id="u1",
        query="什么样的工作氛围更适合我",
        purpose=MemoryQueryPurpose.PLANNING,
    )

    assert [item.id for item in result.records] == [stored.id]
    assert result.relevance[stored.id] > 0


def test_broad_recall_does_not_implicitly_unlock_sensitive_memory(tmp_path) -> None:
    memories = service(tmp_path)
    ordinary = memories.create_explicit(
        owner_id="u1",
        memory_type=MemoryType.PREFERENCE,
        content="我更看重稳定节奏",
    )
    sensitive = memories.create_explicit(
        owner_id="u1",
        memory_type=MemoryType.FACT,
        content="我有一项病史",
        sensitivity=MemorySensitivity.SENSITIVE,
    )
    memories.confirm("u1", sensitive.id, expected_version=sensitive.version)

    result = memories.search_context(
        owner_id="u1",
        query="你记得我的情况吗",
        purpose=MemoryQueryPurpose.PLANNING,
        broad_recall=True,
    )

    assert ordinary.id in {item.id for item in result.records}
    assert sensitive.id not in {item.id for item in result.records}


def test_explicit_correction_supersedes_related_active_memory(tmp_path) -> None:
    memories = service(tmp_path)
    old = memories.create_explicit(
        owner_id="u1",
        memory_type=MemoryType.PREFERENCE,
        content="我更喜欢稳定的大组织",
    )

    new = memories.remember_from_conversation(
        owner_id="u1",
        memory_type=MemoryType.PREFERENCE,
        content="更正一下，我不再喜欢稳定的大组织",
        sensitivity=MemorySensitivity.NORMAL,
        importance=4,
        source_reference="turn-2",
        correction=True,
    )

    assert memories.get("u1", old.id).status is MemoryStatus.SUPERSEDED
    assert memories.store.list_relations("u1", new.id) == (
        (new.id, old.id, "supersedes"),
    )
