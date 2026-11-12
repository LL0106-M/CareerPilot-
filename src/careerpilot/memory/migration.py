from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

from careerpilot.memory.admission_policy import MemorySafetyPrefilter, SafetyFlag
from careerpilot.memory.contracts import AdmissionDecision, PatchOperation
from careerpilot.memory.models import MemoryStatus, ProviderSyncState
from careerpilot.memory.service import MemoryService

MIGRATION_VERSION = "governed-memory-v1"


@dataclass(frozen=True, slots=True)
class MigrationReport:
    dry_run: bool
    scanned: int = 0
    safe_enqueued: int = 0
    quarantined: int = 0
    deduplicated: int = 0
    skipped: int = 0
    reason_counts: dict[str, int] = field(default_factory=dict)


class GovernedMemoryMigrator:
    """Classify legacy rows without hard deletion or automatic remote deletion."""

    def __init__(
        self,
        memory_service: MemoryService,
        prefilter: MemorySafetyPrefilter | None = None,
    ) -> None:
        self._service = memory_service
        self._store = memory_service.store
        self._prefilter = prefilter or MemorySafetyPrefilter()

    def run(self, *, dry_run: bool = True) -> MigrationReport:
        rows = self._store.connection.execute(
            """SELECT owner_id, id FROM memory_records
            WHERE status != 'deleted' ORDER BY owner_id, created_at, rowid"""
        ).fetchall()
        scanned = safe_enqueued = quarantined = deduplicated = skipped = 0
        reasons: dict[str, int] = {}
        seen: dict[tuple[str, str, str], str] = {}

        for row in rows:
            scanned += 1
            owner_id = row["owner_id"]
            memory_id = row["id"]
            receipt = f"migration:{MIGRATION_VERSION}:{memory_id}"
            record = self._store.get_memory(owner_id, memory_id, include_deleted=True)
            key = (owner_id, record.type.value, _normalize(record.content))
            if not dry_run and self._store.has_patch_audit(owner_id, receipt):
                skipped += 1
                _increment(reasons, "already_migrated")
                seen.setdefault(key, memory_id)
                continue

            safety = self._prefilter.inspect(record.content)
            if SafetyFlag.PROMPT_INJECTION in safety.flags or SafetyFlag.CREDENTIAL in safety.flags:
                quarantined += 1
                reason = (
                    "credential_material"
                    if SafetyFlag.CREDENTIAL in safety.flags
                    else "prompt_injection"
                )
                _increment(reasons, reason)
                if not dry_run:
                    if record.status is MemoryStatus.ACTIVE:
                        self._store.transition_memory(
                            owner_id,
                            memory_id,
                            expected_version=record.version,
                            target=MemoryStatus.PAUSED,
                            actor_kind="migration",
                        )
                    self._audit(
                        owner_id,
                        receipt,
                        PatchOperation.UPDATE,
                        AdmissionDecision.REJECT,
                        reason,
                        memory_id,
                    )
                continue

            duplicate_of = seen.get(key)
            if duplicate_of is not None and record.status is MemoryStatus.ACTIVE:
                deduplicated += 1
                _increment(reasons, "exact_duplicate")
                if not dry_run:
                    self._store.transition_memory(
                        owner_id,
                        memory_id,
                        expected_version=record.version,
                        target=MemoryStatus.SUPERSEDED,
                        actor_kind="migration",
                    )
                    self._store.add_relation(owner_id, duplicate_of, memory_id, "deduplicates")
                    self._audit(
                        owner_id,
                        receipt,
                        PatchOperation.SUPERSEDE,
                        AdmissionDecision.IGNORE,
                        "exact_duplicate",
                        memory_id,
                    )
                continue
            seen.setdefault(key, memory_id)

            if record.status is MemoryStatus.ACTIVE:
                safe_enqueued += 1
                _increment(reasons, "safe_active")
                if not dry_run:
                    self._store.upsert_provider_sync(
                        owner_id,
                        memory_id,
                        state=ProviderSyncState.PENDING,
                        content_hash=sha256(record.content.encode("utf-8")).hexdigest(),
                    )
                    self._audit(
                        owner_id,
                        receipt,
                        PatchOperation.NOOP,
                        AdmissionDecision.COMMIT,
                        "safe_active",
                        memory_id,
                    )
            else:
                skipped += 1
                _increment(reasons, f"status_{record.status.value}")
                if not dry_run:
                    self._audit(
                        owner_id,
                        receipt,
                        PatchOperation.NOOP,
                        AdmissionDecision.IGNORE,
                        f"status_{record.status.value}",
                        memory_id,
                    )

        return MigrationReport(
            dry_run=dry_run,
            scanned=scanned,
            safe_enqueued=safe_enqueued,
            quarantined=quarantined,
            deduplicated=deduplicated,
            skipped=skipped,
            reason_counts=reasons,
        )

    def _audit(
        self,
        owner_id: str,
        receipt: str,
        operation: PatchOperation,
        decision: AdmissionDecision,
        reason: str,
        memory_id: str,
    ) -> None:
        self._store.record_patch_audit(
            owner_id=owner_id,
            source_turn_id=receipt,
            operation=operation,
            decision=decision,
            reason_code=reason,
            result_memory_id=memory_id,
        )


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _increment(values: dict[str, int], key: str) -> None:
    values[key] = values.get(key, 0) + 1
