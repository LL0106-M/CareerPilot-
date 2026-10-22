from dataclasses import dataclass

from careerpilot.memory.base import MemoryContext, MemoryStore, MemoryStoreError
from careerpilot.memory.dreaming import (
    CognitiveStore,
    DreamingSnapshot,
    DreamingTriggerPolicy,
)
from careerpilot.memory.write_policy import MemoryWritePolicy


@dataclass(frozen=True, slots=True)
class MemoryCommitResult:
    write_status: str
    consolidation_status: str


class MemoryLifecycle:
    """Post-turn memory admission and asynchronous consolidation boundary."""

    def __init__(
        self,
        memory_store: MemoryStore,
        write_policy: MemoryWritePolicy | None = None,
        cognitive_store: CognitiveStore | None = None,
        dreaming_trigger_policy: DreamingTriggerPolicy | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._write_policy = write_policy or MemoryWritePolicy()
        self._cognitive_store = cognitive_store
        self._trigger_policy = dreaming_trigger_policy or DreamingTriggerPolicy()

    async def commit_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        memories: MemoryContext,
    ) -> MemoryCommitResult:
        write_status = "skipped"
        if self._write_policy.should_write(user_message):
            write_status = "accepted"
            try:
                await self._memory_store.add_turn(
                    user_id,
                    conversation_id,
                    user_message,
                    assistant_message,
                )
            except MemoryStoreError:
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

        return MemoryCommitResult(write_status, consolidation_status)
