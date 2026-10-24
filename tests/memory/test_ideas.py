import pytest

from careerpilot.memory.ideas import (
    IdeaService,
    IdeaStage,
    IdeaStorageDeniedError,
    StorageAuthorization,
)
from careerpilot.memory.models import MemorySensitivity, MemoryStatus
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import MemoryVersionConflictError, SqliteUnifiedMemoryStore


def idea_service(tmp_path) -> IdeaService:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    return IdeaService(MemoryService(store))


def test_explicit_authorized_idea_creates_active_memory_and_projection(tmp_path) -> None:
    ideas = idea_service(tmp_path)

    item = ideas.capture_explicit(
        owner_id="u1",
        raw_text="做一个帮助求职者复盘面试的小工具",
        title="面试复盘工具",
        authorization=StorageAuthorization.GRANTED,
        source_reference="turn-1",
    )

    assert item.stage is IdeaStage.CAPTURED
    assert item.authorization is StorageAuthorization.GRANTED
    assert ideas.memories.get("u1", item.memory_id).status is MemoryStatus.ACTIVE


def test_inferred_idea_requires_candidate_capture_authorization(tmp_path) -> None:
    ideas = idea_service(tmp_path)

    with pytest.raises(IdeaStorageDeniedError):
        ideas.propose(
            owner_id="u1",
            raw_text="用户也许想做求职知识库",
            title="求职知识库",
            authorization=StorageAuthorization.DENIED,
        )

    assert ideas.list("u1") == ()
    candidate = ideas.propose(
        owner_id="u1",
        raw_text="用户也许想做求职知识库",
        title="求职知识库",
        authorization=StorageAuthorization.CANDIDATE_ONLY,
    )
    assert ideas.memories.get("u1", candidate.memory_id).status is MemoryStatus.CANDIDATE


def test_sensitive_explicit_idea_stays_candidate(tmp_path) -> None:
    ideas = idea_service(tmp_path)

    item = ideas.capture_explicit(
        owner_id="u1",
        raw_text="根据我的病史设计求职安排",
        title="健康约束下的求职安排",
        authorization=StorageAuthorization.GRANTED,
        sensitivity=MemorySensitivity.SENSITIVE,
    )

    assert ideas.memories.get("u1", item.memory_id).status is MemoryStatus.CANDIDATE


def test_idea_owner_scope_duplicate_and_stage_versioning(tmp_path) -> None:
    ideas = idea_service(tmp_path)
    item = ideas.capture_explicit(
        owner_id="u1",
        raw_text="研究 AI 产品岗位",
        title="AI 产品岗位研究",
        authorization=StorageAuthorization.GRANTED,
    )
    duplicate = ideas.capture_explicit(
        owner_id="u1",
        raw_text="  研究 AI 产品岗位  ",
        title="新的标题不覆盖原始投影",
        authorization=StorageAuthorization.GRANTED,
    )

    assert duplicate.id == item.id
    assert ideas.list("u2") == ()
    incubating = ideas.update_stage(
        "u1", item.id, expected_version=1, stage=IdeaStage.INCUBATING
    )
    assert incubating.version == 2
    with pytest.raises(MemoryVersionConflictError):
        ideas.update_stage("u1", item.id, expected_version=1, stage=IdeaStage.ACTIONABLE)


def test_action_link_only_records_governed_reference(tmp_path) -> None:
    ideas = idea_service(tmp_path)
    item = ideas.capture_explicit(
        owner_id="u1",
        raw_text="建立一份飞书调研文档",
        title="调研文档",
        authorization=StorageAuthorization.GRANTED,
    )
    actionable = ideas.update_stage(
        "u1", item.id, expected_version=1, stage=IdeaStage.ACTIONABLE
    )

    linked = ideas.link_action(
        "u1",
        item.id,
        expected_version=actionable.version,
        action_reference="action-confirmed-1",
    )

    assert linked.action_reference == "action-confirmed-1"
    assert linked.stage is IdeaStage.ACTIONABLE
