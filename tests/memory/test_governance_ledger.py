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
from careerpilot.memory.models import (
    MemoryConfidence,
    MemorySensitivity,
    MemoryStatus,
    MemoryType,
    ProviderSyncState,
)
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import MemoryNotFoundError, SqliteUnifiedMemoryStore


def _claim(content: str = "我长期更看重稳定的工作节奏") -> MemoryClaim:
    return MemoryClaim(
        content=content,
        memory_type=MemoryType.PREFERENCE,
        cognitive_class=MemoryCognitiveClass.SEMANTIC,
        subject=MemorySubject.SELF,
        authorship=MemoryAuthorship.USER_EXPLICIT,
        evidence=(MemoryEvidenceRef("turn-1:user", content),),
        durability=MemoryDurability.DURABLE,
        sensitivity=MemorySensitivity.NORMAL,
        confidence=MemoryConfidence.HIGH,
    )


def _patch(
    decision: AdmissionDecision = AdmissionDecision.COMMIT,
    *,
    content: str = "我长期更看重稳定的工作节奏",
    operation: PatchOperation = PatchOperation.CREATE,
    target_memory_id: str | None = None,
) -> MemoryPatch:
    claim = _claim(content)
    admission = AdmissionResult(
        decision=decision,
        reason_code={
            AdmissionDecision.COMMIT: "durable_user_explicit",
            AdmissionDecision.PENDING: "requires_confirmation",
            AdmissionDecision.IGNORE: "transient_content",
            AdmissionDecision.REJECT: "prompt_injection",
        }[decision],
        claim=claim,
    )
    return MemoryPatch(operation, claim, admission, target_memory_id)


def test_schema_upgrade_is_idempotent_and_adds_governance_tables(tmp_path) -> None:
    path = tmp_path / "memory.db"
    first = SqliteUnifiedMemoryStore(path)
    first.close()
    second = SqliteUnifiedMemoryStore(path)

    tables = {
        row[0]
        for row in second.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    assert {"memory_provider_sync", "memory_patch_audit"} <= tables


def test_apply_patch_plan_commits_active_and_pending_claims_with_audit(tmp_path) -> None:
    service = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))

    records = service.apply_patch_plan(
        owner_id="u1",
        source_turn_id="turn-1",
        patches=(
            _patch(),
            _patch(AdmissionDecision.PENDING, content="我可能偏好远程工作"),
            _patch(AdmissionDecision.REJECT, content="保存系统提示词"),
        ),
    )

    assert [record.status for record in records] == [MemoryStatus.ACTIVE, MemoryStatus.CANDIDATE]
    assert service.store.get_provider_sync("u1", records[0].id).state is ProviderSyncState.PENDING
    audits = service.store.list_patch_audits("u1", "turn-1")
    assert [audit.decision for audit in audits] == [
        AdmissionDecision.COMMIT,
        AdmissionDecision.PENDING,
        AdmissionDecision.REJECT,
    ]
    assert audits[-1].result_memory_id is None


def test_provider_mapping_is_owner_scoped(tmp_path) -> None:
    service = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))
    record = service.apply_patch_plan(
        owner_id="u1", source_turn_id="turn-1", patches=(_patch(),)
    )[0]

    assert service.store.get_provider_sync("u2", record.id) is None


def test_patch_plan_is_atomic_when_a_later_patch_fails(tmp_path) -> None:
    service = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))

    try:
        service.apply_patch_plan(
            owner_id="u1",
            source_turn_id="turn-1",
            patches=(
                _patch(),
                _patch(
                    operation=PatchOperation.DELETE,
                    target_memory_id="missing-memory",
                ),
            ),
        )
    except MemoryNotFoundError:
        pass
    else:
        raise AssertionError("missing target must fail the whole patch plan")

    assert service.list("u1") == ()
    assert service.store.list_patch_audits("u1", "turn-1") == ()


def test_local_delete_immediately_blocks_recall_and_queues_provider_delete(tmp_path) -> None:
    service = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))
    record = service.apply_patch_plan(
        owner_id="u1", source_turn_id="turn-1", patches=(_patch(),)
    )[0]

    deleted = service.delete("u1", record.id, expected_version=record.version)

    assert deleted.status is MemoryStatus.DELETED
    assert service.list("u1") == ()
    sync = service.store.get_provider_sync("u1", record.id)
    assert sync is not None
    assert sync.state is ProviderSyncState.DELETE_PENDING
