from dataclasses import dataclass

from careerpilot.agent.prompt import PromptComposer
from careerpilot.memory.base import (
    MemoryContext,
    MemoryRetrievalMode,
    MemoryStore,
    MemoryStoreError,
)
from careerpilot.memory.dreaming import CognitiveStore
from careerpilot.support.policy import SupportDecision, SupportMode, SupportPolicy


@dataclass(frozen=True, slots=True)
class ContextRequest:
    user_id: str
    conversation_id: str
    message: str
    requested_mode: SupportMode | None = None


@dataclass(frozen=True, slots=True)
class CompiledContext:
    system_prompt: str
    decision: SupportDecision
    memories: MemoryContext
    memory_read_status: str
    allowed_tool_names: frozenset[str]


class CareerContextCompiler:
    """Intent-aware context assembly across MemOS and cognitive state."""

    def __init__(
        self,
        memory_store: MemoryStore,
        support_policy: SupportPolicy,
        prompt_composer: PromptComposer | None = None,
        cognitive_store: CognitiveStore | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._support_policy = support_policy
        self._prompt_composer = prompt_composer or PromptComposer()
        self._cognitive_store = cognitive_store

    async def compile(self, request: ContextRequest) -> CompiledContext:
        decision = self._support_policy.decide(request.message, request.requested_mode)
        memory_read_status = "available"
        try:
            memories = await self._memory_store.search(
                request.user_id,
                request.conversation_id,
                request.message,
                mode=(
                    MemoryRetrievalMode.COMPANION
                    if decision.mode is SupportMode.LISTEN
                    else MemoryRetrievalMode.PLANNING
                ),
            )
        except MemoryStoreError:
            memories = MemoryContext()
            memory_read_status = "unavailable"

        hypotheses = ()
        if self._cognitive_store is not None:
            try:
                hypotheses = self._cognitive_store.list_hypotheses(request.user_id)
            except Exception:
                hypotheses = ()

        return CompiledContext(
            system_prompt=self._prompt_composer.compose(decision, memories, hypotheses),
            decision=decision,
            memories=memories,
            memory_read_status=memory_read_status,
            allowed_tool_names=(
                frozenset()
                if decision.mode is SupportMode.LISTEN
                else frozenset({"search_career_knowledge"})
            ),
        )
