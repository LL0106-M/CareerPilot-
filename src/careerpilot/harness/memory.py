from dataclasses import dataclass

from careerpilot.memory.base import MemoryContext, MemoryStore, MemoryStoreError
from careerpilot.memory.dreaming import (
    CognitiveStore,
    DreamingSnapshot,
    DreamingTriggerPolicy,
)
from careerpilot.memory.extractor import (
    MemoryClaimExtractor,
    MemoryExtractionTurn,
    RuleBasedMemoryClaimExtractor,
)
from careerpilot.memory.models import ProviderSyncState
from careerpilot.memory.patch_planner import MemoryPatchPlanner
from careerpilot.memory.provider_service import GovernedMemoryProviderService
from careerpilot.memory.service import MemoryService
from careerpilot.memory.write_policy import MemoryWritePolicy


@dataclass(frozen=True, slots=True)
class MemoryCommitResult:
    write_status: str
    consolidation_status: str
    memory_ids: tuple[str, ...] = ()
    provider_write_status: str = "skipped"


class MemoryLifecycle:
    """Post-turn memory admission and asynchronous consolidation boundary."""

    def __init__(
        self,
        memory_store: MemoryStore,
        write_policy: MemoryWritePolicy | None = None,
        cognitive_store: CognitiveStore | None = None,
        dreaming_trigger_policy: DreamingTriggerPolicy | None = None,
        unified_memory_service: MemoryService | None = None,
        claim_extractor: MemoryClaimExtractor | None = None,
        provider_service: GovernedMemoryProviderService | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._write_policy = write_policy or MemoryWritePolicy()
        self._cognitive_store = cognitive_store
        self._trigger_policy = dreaming_trigger_policy or DreamingTriggerPolicy()
        self._unified_memory_service = unified_memory_service
        self._claim_extractor = claim_extractor or RuleBasedMemoryClaimExtractor(
            self._write_policy
        )
        self._patch_planner = MemoryPatchPlanner()
        self._provider_service = provider_service
        if provider_service is None and unified_memory_service is not None:
            self._provider_service = GovernedMemoryProviderService(
                unified_memory_service, memory_store
            )

    async def commit_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        memories: MemoryContext,
        turn_id: str | None = None,
    ) -> MemoryCommitResult:
        write_status = "skipped"
        provider_write_status = "skipped"
        memory_ids: list[str] = []
        try:
            claims = await self._claim_extractor.extract(
                MemoryExtractionTurn(
                    turn_id=turn_id or conversation_id,
                    user_message=user_message,
                    assistant_message=assistant_message,
                )
            )
        except Exception:
            claims = ()
            write_status = "unavailable"
        if claims and self._unified_memory_service is not None:
            try:
                active = self._unified_memory_service.store.list_active_memories(user_id, limit=200)
                patches = self._patch_planner.plan(user_id, claims, active)
                records = self._unified_memory_service.apply_patch_plan(
                    owner_id=user_id,
                    source_turn_id=turn_id or conversation_id,
                    patches=patches,
                )
                memory_ids.extend(record.id for record in records)
                write_status = "accepted" if records else "skipped"
                if self._memory_store.enabled and self._provider_service is not None:
                    await self._provider_service.sync_pending(user_id, conversation_id)
                    states = tuple(
                        sync.state
                        for memory_id in memory_ids
                        if (
                            sync := self._unified_memory_service.store.get_provider_sync(
                                user_id, memory_id
                            )
                        )
                        is not None
                    )
                    provider_write_status = (
                        "unavailable"
                        if ProviderSyncState.FAILED in states
                        else "pending"
                    )
            except (MemoryStoreError, Exception):
                write_status = "unavailable"

        consolidation_status = "skipped"
        trigger = self._trigger_policy.detect(user_message)
        if trigger is not None:
            if self._cognitive_store is None:
                consolidation_status = "unavailable"
            else:
                try:
                    self._cognitive_store.enqueue(
                        DreamingSnapshot.from_turn(
                            user_id=user_id,
                            conversation_id=conversation_id,
                            trigger=trigger,
                            user_message=user_message,
                            assistant_message=assistant_message,
                            memories=memories,
                        )
                    )
                    consolidation_status = "queued"
                except Exception:
                    consolidation_status = "unavailable"

        return MemoryCommitResult(
            write_status,
            consolidation_status,
            tuple(memory_ids),
            provider_write_status,
        )
