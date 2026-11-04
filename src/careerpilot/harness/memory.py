from dataclasses import dataclass

from careerpilot.memory.base import MemoryContext, MemoryStore, MemoryStoreError
from careerpilot.memory.dreaming import (
    CognitiveStore,
    DreamingSnapshot,
    DreamingTriggerPolicy,
)
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
    ) -> None:
        self._memory_store = memory_store
        self._write_policy = write_policy or MemoryWritePolicy()
        self._cognitive_store = cognitive_store
        self._trigger_policy = dreaming_trigger_policy or DreamingTriggerPolicy()
        self._unified_memory_service = unified_memory_service

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
        candidates = self._write_policy.extract(user_message)
        if candidates:
            try:
                if self._unified_memory_service is not None:
                    records = self._unified_memory_service.remember_many_from_conversation(
                        owner_id=user_id,
                        candidates=candidates,
                        source_reference=turn_id or conversation_id,
                    )
                    memory_ids.extend(record.id for record in records)
                    write_status = "accepted"
                    if self._memory_store.enabled:
                        try:
                            await self._memory_store.add_turn(
                                user_id,
                                conversation_id,
                                user_message,
                                assistant_message,
                            )
                            provider_write_status = "synced"
                        except (MemoryStoreError, Exception):
                            provider_write_status = "unavailable"
                else:
                    # Compatibility path for deployments that have not enabled the
                    # authoritative local memory store yet.
                    await self._memory_store.add_turn(
                        user_id,
                        conversation_id,
                        user_message,
                        assistant_message,
                    )
                    write_status = "accepted"
                    provider_write_status = (
                        "synced" if self._memory_store.enabled else "skipped"
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
