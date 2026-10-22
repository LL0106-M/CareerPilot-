from dataclasses import dataclass

from careerpilot.agent.prompt import PromptComposer
from careerpilot.context.contracts import (
    IntentFrame,
    IntentInterpreter,
    RetrievalPlan,
    RetrievalRouter,
    RetrievalSource,
)
from careerpilot.context.intent import RuleBasedIntentInterpreter
from careerpilot.context.router import IntentAwareRetrievalRouter
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
    intent: IntentFrame
    retrieval_plan: RetrievalPlan
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
        intent_interpreter: IntentInterpreter | None = None,
        retrieval_router: RetrievalRouter | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._prompt_composer = prompt_composer or PromptComposer()
        self._cognitive_store = cognitive_store
        self._intent_interpreter = intent_interpreter or RuleBasedIntentInterpreter(
            support_policy
        )
        self._retrieval_router = retrieval_router or IntentAwareRetrievalRouter()

    async def compile(self, request: ContextRequest) -> CompiledContext:
        intent = await self._intent_interpreter.interpret(
            request.message, request.requested_mode
        )
        decision = intent.support
        retrieval_plan = self._retrieval_router.plan(intent, request.message)
        memory_read_status = "skipped"
        memories = MemoryContext()
        if retrieval_plan.uses(RetrievalSource.MEMORY):
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
                memory_read_status = "unavailable"

        hypotheses = ()
        if self._cognitive_store is not None and retrieval_plan.uses(
            RetrievalSource.COGNITIVE_STATE
        ):
            try:
                hypotheses = self._cognitive_store.list_hypotheses(request.user_id)
            except Exception:
                hypotheses = ()

        return CompiledContext(
            system_prompt=self._prompt_composer.compose(
                decision,
                memories,
                hypotheses,
                intent,
                retrieval_plan,
            ),
            decision=decision,
            intent=intent,
            retrieval_plan=retrieval_plan,
            memories=memories,
            memory_read_status=memory_read_status,
            allowed_tool_names=retrieval_plan.allowed_tool_names,
        )
