from datetime import UTC, datetime, timedelta

import pytest

from careerpilot.memory.models import (
    MemoryConfidence,
    MemoryOrigin,
    MemorySensitivity,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
    MemoryUsageType,
)
from careerpilot.memory.unified_store import (
    MemoryNotFoundError,
    MemoryVersionConflictError,
    SqliteUnifiedMemoryStore,
)


def create_memory(store: SqliteUnifiedMemoryStore, owner_id: str = "u1"):
    return store.create_memory(
        owner_id=owner_id,
        memory_type=MemoryType.IDEA,
        content="做一个面试复盘工具",
        status=MemoryStatus.ACTIVE,
        sensitivity=MemorySensitivity.NORMAL,
        origin=MemoryOrigin.USER_EXPLICIT,
        source_type=MemorySourceType.CONVERSATION,
        source_reference="turn-1",
        confidence=MemoryConfidence.HIGH,
    )


def test_store_hides_cross_owner_memory(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memory = create_memory(store)

    with pytest.raises(MemoryNotFoundError):
        store.get_memory("u2", memory.id)


def test_store_preserves_revision_and_rejects_stale_version(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memory = create_memory(store)

    updated = store.update_memory(
        "u1", memory.id, expected_version=1, content="做一个 AI 面试复盘工具"
    )

    assert updated.version == 2
    assert updated.content == "做一个 AI 面试复盘工具"
    revisions = store.list_revisions("u1", memory.id)
    assert [(item.from_version, item.to_version) for item in revisions] == [(1, 2)]
    assert revisions[0].before["content"] == "做一个面试复盘工具"
    with pytest.raises(MemoryVersionConflictError):
        store.update_memory("u1", memory.id, expected_version=1, content="过期写入")


def test_store_enforces_lifecycle_and_soft_delete(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memory = create_memory(store)

    paused = store.transition_memory(
        "u1", memory.id, expected_version=1, target=MemoryStatus.PAUSED
    )
    resumed = store.transition_memory(
        "u1", memory.id, expected_version=paused.version, target=MemoryStatus.ACTIVE
    )
    deleted = store.transition_memory(
        "u1", memory.id, expected_version=resumed.version, target=MemoryStatus.DELETED
    )

    assert deleted.deleted_at is not None
    assert store.list_memories("u1", statuses=(MemoryStatus.ACTIVE,)) == ()
    with pytest.raises(ValueError, match="Invalid memory transition"):
        store.transition_memory(
            "u1", memory.id, expected_version=deleted.version, target=MemoryStatus.ACTIVE
        )


def test_store_filters_expired_memory_from_active_context(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    expired = datetime.now(UTC) - timedelta(minutes=1)
    store.create_memory(
        owner_id="u1",
        memory_type=MemoryType.CONSTRAINT,
        content="今天不安排面试",
        status=MemoryStatus.ACTIVE,
        sensitivity=MemorySensitivity.NORMAL,
        origin=MemoryOrigin.USER_EXPLICIT,
        source_type=MemorySourceType.CONVERSATION,
        confidence=MemoryConfidence.HIGH,
        expires_at=expired,
    )

    assert store.list_active_memories("u1") == ()


def test_evidence_and_usage_are_owner_scoped_and_usage_updates_last_used(tmp_path) -> None:
    store = SqliteUnifiedMemoryStore(tmp_path / "memory.db")
    memory = create_memory(store)

    evidence = store.add_evidence(
        "u1",
        memory.id,
        kind="user_statement",
        source_reference="turn-1",
        excerpt="我想做一个面试复盘工具",
    )
    usage = store.record_usage(
        "u1",
        memory.id,
        turn_id="turn-2",
        usage_type=MemoryUsageType.ANSWER_CONTEXT,
    )

    assert evidence.memory_id == memory.id
    assert usage.memory_id == memory.id
    assert store.get_memory("u1", memory.id).last_used_at is not None
    assert store.list_evidence("u1", memory.id)[0].excerpt == "我想做一个面试复盘工具"
    with pytest.raises(MemoryNotFoundError):
        store.record_usage(
            "u2",
            memory.id,
            turn_id="turn-x",
            usage_type=MemoryUsageType.ANSWER_CONTEXT,
        )
