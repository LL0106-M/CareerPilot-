from datetime import UTC, datetime

from careerpilot.memory.contracts import (
    AdmissionDecision,
    MemoryAuthorship,
    MemoryClaim,
    MemoryCognitiveClass,
    MemoryDurability,
    MemoryEvidenceRef,
    MemorySubject,
    PatchOperation,
)
from careerpilot.memory.models import (
    MemoryConfidence,
    MemoryOrigin,
    MemoryRecord,
    MemorySensitivity,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)
from careerpilot.memory.patch_planner import MemoryPatchPlanner


def _claim(content: str, **changes: object) -> MemoryClaim:
    values: dict[str, object] = {
        "content": content,
        "memory_type": MemoryType.PREFERENCE,
        "cognitive_class": MemoryCognitiveClass.SEMANTIC,
        "subject": MemorySubject.SELF,
        "authorship": MemoryAuthorship.USER_EXPLICIT,
        "evidence": (MemoryEvidenceRef("turn-1:user", content),),
        "durability": MemoryDurability.DURABLE,
        "sensitivity": MemorySensitivity.NORMAL,
        "confidence": MemoryConfidence.HIGH,
    }
    values.update(changes)
    return MemoryClaim(**values)


def _record(memory_id: str, content: str) -> MemoryRecord:
    now = datetime.now(UTC)
    return MemoryRecord(
        id=memory_id,
        owner_id="owner-1",
        type=MemoryType.PREFERENCE,
        content=content,
        status=MemoryStatus.ACTIVE,
        sensitivity=MemorySensitivity.NORMAL,
        origin=MemoryOrigin.USER_EXPLICIT,
        source_type=MemorySourceType.CONVERSATION,
        source_reference="turn-0",
        confidence=MemoryConfidence.HIGH,
        importance=3,
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_exact_duplicate_becomes_noop() -> None:
    patches = MemoryPatchPlanner().plan(
        "owner-1",
        (_claim("我长期更看重稳定的工作节奏"),),
        (_record("memory-1", "我长期更看重稳定的工作节奏"),),
    )

    assert patches[0].operation is PatchOperation.NOOP
    assert patches[0].target_memory_id == "memory-1"


def test_explicit_targeted_correction_supersedes_only_named_memory() -> None:
    claim = _claim(
        "我现在更喜欢线下协作",
        correction_hint="把远程偏好改为线下协作",
        target_memory_id="memory-remote",
    )
    patches = MemoryPatchPlanner().plan(
        "owner-1",
        (claim,),
        (
            _record("memory-remote", "我更喜欢远程工作"),
            _record("memory-stable", "我更看重稳定节奏"),
        ),
    )

    assert patches[0].operation is PatchOperation.SUPERSEDE
    assert patches[0].target_memory_id == "memory-remote"


def test_unresolved_correction_conflict_stays_pending() -> None:
    claim = _claim("我现在更喜欢混合办公", correction_hint="更新工作方式偏好")
    patches = MemoryPatchPlanner().plan(
        "owner-1",
        (claim,),
        (
            _record("memory-remote", "我更喜欢远程工作"),
            _record("memory-onsite", "我更喜欢线下协作"),
        ),
    )

    assert patches[0].operation is PatchOperation.CREATE
    assert patches[0].admission.decision is AdmissionDecision.PENDING
    assert patches[0].admission.reason_code == "conflict_requires_confirmation"


def test_new_unrelated_claim_is_created_without_token_fuzzy_supersession() -> None:
    patches = MemoryPatchPlanner().plan(
        "owner-1",
        (_claim("我喜欢在早晨做深度工作"),),
        (_record("memory-1", "我喜欢远程工作"),),
    )

    assert patches[0].operation is PatchOperation.CREATE
    assert patches[0].target_memory_id is None
