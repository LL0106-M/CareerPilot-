from dataclasses import FrozenInstanceError

import pytest

from careerpilot.memory.contracts import (
    AdmissionDecision,
    AdmissionResult,
    MemoryAuthorship,
    MemoryClaim,
    MemoryCognitiveClass,
    MemoryDurability,
    MemoryEvidenceRef,
    MemoryPatch,
    MemorySubject,
    PatchOperation,
)
from careerpilot.memory.models import MemoryConfidence, MemorySensitivity, MemoryType


def _claim(**changes: object) -> MemoryClaim:
    values: dict[str, object] = {
        "content": "我长期更看重稳定的工作节奏",
        "memory_type": MemoryType.PREFERENCE,
        "cognitive_class": MemoryCognitiveClass.SEMANTIC,
        "subject": MemorySubject.SELF,
        "authorship": MemoryAuthorship.USER_EXPLICIT,
        "evidence": (
            MemoryEvidenceRef(message_id="turn-1:user", excerpt="我长期更看重稳定的工作节奏"),
        ),
        "durability": MemoryDurability.DURABLE,
        "sensitivity": MemorySensitivity.NORMAL,
        "confidence": MemoryConfidence.HIGH,
    }
    values.update(changes)
    return MemoryClaim(**values)


def test_claim_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        _claim(evidence=())


def test_claim_normalizes_content_and_bounds_evidence() -> None:
    claim = _claim(
        content="  我长期  更看重稳定的工作节奏  ",
        evidence=(MemoryEvidenceRef(message_id="turn-1:user", excerpt="x" * 800),),
    )

    assert claim.content == "我长期 更看重稳定的工作节奏"
    assert len(claim.evidence[0].excerpt) == 500


@pytest.mark.parametrize("content", ["", "   ", "x" * 1001])
def test_claim_rejects_empty_or_oversized_content(content: str) -> None:
    with pytest.raises(ValueError, match="content"):
        _claim(content=content)


def test_contracts_are_immutable() -> None:
    claim = _claim()

    with pytest.raises(FrozenInstanceError):
        claim.content = "changed"  # type: ignore[misc]


def test_admission_and_patch_contracts_preserve_stable_reason_codes() -> None:
    claim = _claim()
    admission = AdmissionResult(
        decision=AdmissionDecision.COMMIT,
        reason_code="durable_user_explicit",
        claim=claim,
    )
    patch = MemoryPatch(
        operation=PatchOperation.CREATE,
        claim=claim,
        admission=admission,
        target_memory_id=None,
    )

    assert admission.reason_code == "durable_user_explicit"
    assert patch.operation is PatchOperation.CREATE


def test_patch_target_is_required_for_mutating_existing_memory() -> None:
    claim = _claim()
    admission = AdmissionResult(
        decision=AdmissionDecision.COMMIT,
        reason_code="explicit_correction",
        claim=claim,
    )

    with pytest.raises(ValueError, match="target_memory_id"):
        MemoryPatch(
            operation=PatchOperation.SUPERSEDE,
            claim=claim,
            admission=admission,
        )
