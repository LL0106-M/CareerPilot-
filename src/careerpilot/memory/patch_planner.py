from __future__ import annotations

from careerpilot.memory.admission_policy import MemoryAdmissionGate
from careerpilot.memory.contracts import (
    AdmissionDecision,
    AdmissionReason,
    AdmissionResult,
    MemoryClaim,
    MemoryPatch,
    PatchOperation,
)
from careerpilot.memory.models import MemoryRecord, MemoryStatus


class MemoryPatchPlanner:
    def __init__(self, admission_gate: MemoryAdmissionGate | None = None) -> None:
        self._admission_gate = admission_gate or MemoryAdmissionGate()

    def plan(
        self,
        owner_id: str,
        claims: tuple[MemoryClaim, ...],
        active_records: tuple[MemoryRecord, ...],
    ) -> tuple[MemoryPatch, ...]:
        active = tuple(
            record
            for record in active_records
            if record.owner_id == owner_id and record.status is MemoryStatus.ACTIVE
        )
        patches: list[MemoryPatch] = []
        for claim in claims:
            source_text = "\n".join(item.excerpt for item in claim.evidence)
            admission = self._admission_gate.decide(claim, source_text)
            duplicate = next(
                (
                    record
                    for record in active
                    if record.type is claim.memory_type
                    and _normalize(record.content) == _normalize(claim.content)
                ),
                None,
            )
            if duplicate is not None:
                patches.append(
                    MemoryPatch(
                        operation=PatchOperation.NOOP,
                        claim=claim,
                        admission=admission,
                        target_memory_id=duplicate.id,
                    )
                )
                continue

            target = next(
                (record for record in active if record.id == claim.target_memory_id),
                None,
            )
            if target is not None and target.type is claim.memory_type:
                patches.append(
                    MemoryPatch(
                        operation=PatchOperation.SUPERSEDE,
                        claim=claim,
                        admission=admission,
                        target_memory_id=target.id,
                    )
                )
                continue

            same_type = tuple(record for record in active if record.type is claim.memory_type)
            if claim.correction_hint and same_type:
                admission = AdmissionResult(
                    decision=AdmissionDecision.PENDING,
                    reason_code=AdmissionReason.CONFLICT_REQUIRES_CONFIRMATION.value,
                    claim=claim,
                )
            patches.append(
                MemoryPatch(
                    operation=PatchOperation.CREATE,
                    claim=claim,
                    admission=admission,
                )
            )
        return tuple(patches)


def _normalize(content: str) -> str:
    return " ".join(content.split()).casefold()
