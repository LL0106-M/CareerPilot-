from careerpilot.memory.base import MemoryContext, MemoryItem
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
    MemoryType,
    ProviderSyncState,
)
from careerpilot.memory.provider_service import GovernedMemoryProviderService
from careerpilot.memory.service import MemoryQueryPurpose, MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore


class FakeProvider:
    enabled = True

    def __init__(self) -> None:
        self.writes: list[dict[str, str]] = []
        self.deletes: list[tuple[str, ...]] = []
        self.search_result = MemoryContext()
        self.fail_writes = False

    async def write_claim(self, **values):  # type: ignore[no-untyped-def]
        if self.fail_writes:
            raise RuntimeError("provider unavailable")
        self.writes.append(values)

    async def search(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.search_result

    async def list_memories(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.search_result

    async def delete_memories(self, user_id, memory_ids):  # type: ignore[no-untyped-def]
        del user_id
        self.deletes.append(memory_ids)


def _service(tmp_path):  # type: ignore[no-untyped-def]
    memory_service = MemoryService(SqliteUnifiedMemoryStore(tmp_path / "memory.db"))
    claim = MemoryClaim(
        content="我长期更看重稳定的工作节奏",
        memory_type=MemoryType.PREFERENCE,
        cognitive_class=MemoryCognitiveClass.SEMANTIC,
        subject=MemorySubject.SELF,
        authorship=MemoryAuthorship.USER_EXPLICIT,
        evidence=(MemoryEvidenceRef("turn-1:user", "我长期更看重稳定的工作节奏"),),
        durability=MemoryDurability.DURABLE,
        sensitivity=MemorySensitivity.NORMAL,
        confidence=MemoryConfidence.HIGH,
    )
    admission = AdmissionResult(AdmissionDecision.COMMIT, "durable_user_explicit", claim)
    record = memory_service.apply_patch_plan(
        owner_id="u1",
        source_turn_id="turn-1",
        patches=(MemoryPatch(PatchOperation.CREATE, claim, admission),),
    )[0]
    provider = FakeProvider()
    return memory_service, provider, GovernedMemoryProviderService(memory_service, provider), record


async def test_pending_claim_sync_is_retryable_and_never_uses_raw_turn(tmp_path) -> None:
    memory_service, provider, governed, record = _service(tmp_path)
    provider.fail_writes = True

    await governed.sync_pending("u1", "thread-1")

    failed = memory_service.store.get_provider_sync("u1", record.id)
    assert failed.state is ProviderSyncState.FAILED
    assert failed.attempt_count == 1
    provider.fail_writes = False
    await governed.sync_pending("u1", "thread-1")
    assert provider.writes[0]["content"] == record.content
    assert set(provider.writes[0]) == {
        "user_id", "conversation_id", "local_memory_id", "content", "memory_type"
    }


async def test_governed_search_excludes_unmapped_cloud_results(tmp_path) -> None:
    _, provider, governed, _ = _service(tmp_path)
    provider.search_result = MemoryContext(
        facts=(MemoryItem("unknown-provider-id", "外部污染记忆", "fact"),)
    )

    result = await governed.search(
        "u1", "thread-1", "稳定", purpose=MemoryQueryPurpose.PLANNING
    )

    assert all(item.content != "外部污染记忆" for item in result.facts)


async def test_governed_search_returns_only_active_mapped_result(tmp_path) -> None:
    memory_service, provider, governed, record = _service(tmp_path)
    memory_service.store.upsert_provider_sync(
        "u1",
        record.id,
        state=ProviderSyncState.SYNCED,
        provider_memory_id="provider-1",
    )
    provider.search_result = MemoryContext(
        facts=(MemoryItem("provider-1", record.content, "preference"),)
    )

    result = await governed.search(
        "u1", "thread-1", "稳定", purpose=MemoryQueryPurpose.PLANNING
    )

    assert [item.id for item in result.facts] == [record.id]


async def test_delete_is_exact_and_local_state_dominates(tmp_path) -> None:
    memory_service, provider, governed, record = _service(tmp_path)
    memory_service.store.upsert_provider_sync(
        "u1", record.id, state=ProviderSyncState.SYNCED, provider_memory_id="provider-1"
    )
    memory_service.delete("u1", record.id, expected_version=record.version)

    await governed.flush_deletes("u1")

    assert provider.deletes == [("provider-1",)]
    sync = memory_service.store.get_provider_sync("u1", record.id)
    assert sync is not None
    assert sync.state is ProviderSyncState.DELETED
