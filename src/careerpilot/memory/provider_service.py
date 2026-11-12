from __future__ import annotations

from careerpilot.memory.base import (
    MemoryContext,
    MemoryItem,
    MemoryRetrievalMode,
    MemoryStore,
)
from careerpilot.memory.models import MemoryStatus, ProviderSyncState
from careerpilot.memory.service import MemoryQueryPurpose, MemoryService


class GovernedMemoryProviderService:
    """Synchronize canonical claims and admit only locally governed cloud results."""

    def __init__(self, memory_service: MemoryService, provider: MemoryStore) -> None:
        self._memory_service = memory_service
        self._provider = provider

    async def sync_pending(self, owner_id: str, conversation_id: str) -> None:
        rows = self._memory_service.store.list_provider_sync(
            owner_id,
            states=(ProviderSyncState.PENDING, ProviderSyncState.FAILED),
            limit=100,
        )
        for sync in rows:
            try:
                record = self._memory_service.get(owner_id, sync.memory_id)
                if record.status is not MemoryStatus.ACTIVE:
                    continue
                await self._provider.write_claim(
                    user_id=owner_id,
                    conversation_id=conversation_id,
                    local_memory_id=record.id,
                    content=record.content,
                    memory_type=record.type.value,
                )
                self._memory_service.store.upsert_provider_sync(
                    owner_id,
                    record.id,
                    state=ProviderSyncState.PENDING,
                    increment_attempt=True,
                    error_code=None,
                )
            except Exception as exc:
                self._memory_service.store.upsert_provider_sync(
                    owner_id,
                    sync.memory_id,
                    state=ProviderSyncState.FAILED,
                    increment_attempt=True,
                    error_code=type(exc).__name__,
                )

    async def reconcile(self, owner_id: str) -> None:
        rows = self._memory_service.store.list_provider_sync(
            owner_id, states=(ProviderSyncState.PENDING,), limit=100
        )
        for sync in rows:
            try:
                context = await self._provider.list_memories(
                    owner_id, local_memory_id=sync.memory_id
                )
            except Exception:
                continue
            items = (*context.facts, *context.preferences)
            match = next((item for item in items if item.id), None)
            if match is not None:
                self._memory_service.store.upsert_provider_sync(
                    owner_id,
                    sync.memory_id,
                    state=ProviderSyncState.SYNCED,
                    provider_memory_id=match.id,
                )

    async def flush_deletes(self, owner_id: str) -> None:
        rows = self._memory_service.store.list_provider_sync(
            owner_id, states=(ProviderSyncState.DELETE_PENDING,), limit=100
        )
        for sync in rows:
            if not sync.provider_memory_id:
                self._memory_service.store.upsert_provider_sync(
                    owner_id, sync.memory_id, state=ProviderSyncState.DELETED
                )
                continue
            try:
                await self._provider.delete_memories(
                    owner_id, (sync.provider_memory_id,)
                )
            except Exception as exc:
                self._memory_service.store.upsert_provider_sync(
                    owner_id,
                    sync.memory_id,
                    state=ProviderSyncState.DELETE_PENDING,
                    increment_attempt=True,
                    error_code=type(exc).__name__,
                )
                continue
            self._memory_service.store.upsert_provider_sync(
                owner_id,
                sync.memory_id,
                state=ProviderSyncState.DELETED,
                increment_attempt=True,
            )

    async def search(
        self,
        owner_id: str,
        conversation_id: str,
        query: str,
        *,
        purpose: MemoryQueryPurpose,
        explicit_personal_recall: bool = False,
        broad_recall: bool = False,
    ) -> MemoryContext:
        try:
            cloud = await self._provider.search(
                owner_id,
                conversation_id,
                query,
                mode=(
                    MemoryRetrievalMode.COMPANION
                    if purpose is MemoryQueryPurpose.COMPANION
                    else MemoryRetrievalMode.PLANNING
                ),
            )
            governed = self._filter_mapped(owner_id, cloud, explicit_personal_recall, purpose)
            if governed.facts or governed.preferences:
                return governed
        except Exception:
            pass
        local = self._memory_service.search_context(
            owner_id=owner_id,
            query=query,
            purpose=purpose,
            explicit_personal_recall=explicit_personal_recall,
            broad_recall=broad_recall,
        )
        facts: list[MemoryItem] = []
        preferences: list[MemoryItem] = []
        for record in local.records:
            item = MemoryItem(
                id=record.id,
                content=record.content,
                kind=record.type.value,
                relevance=local.relevance.get(record.id),
                source="local_fallback",
            )
            (preferences if record.type.value == "preference" else facts).append(item)
        return MemoryContext(tuple(facts), tuple(preferences))

    def _filter_mapped(
        self,
        owner_id: str,
        context: MemoryContext,
        explicit_personal_recall: bool,
        purpose: MemoryQueryPurpose,
    ) -> MemoryContext:
        mappings = {
            row.provider_memory_id: row.memory_id
            for row in self._memory_service.store.list_provider_sync(
                owner_id, states=(ProviderSyncState.SYNCED,), limit=500
            )
            if row.provider_memory_id
        }

        def admit(item: MemoryItem) -> MemoryItem | None:
            local_id = mappings.get(item.id)
            if local_id is None:
                return None
            try:
                record = self._memory_service.get(owner_id, local_id)
            except Exception:
                return None
            if record.status is not MemoryStatus.ACTIVE:
                return None
            if record.sensitivity.value == "sensitive" and (
                not explicit_personal_recall or purpose is MemoryQueryPurpose.ACTION_PREVIEW
            ):
                return None
            return MemoryItem(
                id=record.id,
                content=record.content,
                kind=record.type.value,
                relevance=item.relevance,
                confidence=record.confidence.value,
                source="memos_governed",
                updated_at=item.updated_at,
            )

        return MemoryContext(
            facts=tuple(result for item in context.facts if (result := admit(item)) is not None),
            preferences=tuple(
                result for item in context.preferences if (result := admit(item)) is not None
            ),
        )
