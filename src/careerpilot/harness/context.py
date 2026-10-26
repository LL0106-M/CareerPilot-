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
    MemoryItem,
    MemoryRetrievalMode,
    MemoryStore,
    MemoryStoreError,
)
from careerpilot.memory.dreaming import CognitiveStore
from careerpilot.memory.models import MemoryType
from careerpilot.memory.service import MemoryQueryPurpose, MemoryService
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

    _broad_memory_markers = (
        "记得",
        "记忆",
        "你知道我的",
        "回忆",
        "我的偏好",
        "我的情况",
        "结合我的",
        "根据我的",
    )
    _sensitive_memory_markers = (
        "病史",
        "健康记录",
        "敏感信息",
        "身份证",
        "诊断记录",
    )

    def __init__(
        self,
        memory_store: MemoryStore,
        support_policy: SupportPolicy,
        prompt_composer: PromptComposer | None = None,
        cognitive_store: CognitiveStore | None = None,
        intent_interpreter: IntentInterpreter | None = None,
        retrieval_router: RetrievalRouter | None = None,
        unified_memory_service: MemoryService | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._prompt_composer = prompt_composer or PromptComposer()
        self._cognitive_store = cognitive_store
        self._intent_interpreter = intent_interpreter or RuleBasedIntentInterpreter(
            support_policy
        )
        self._retrieval_router = retrieval_router or IntentAwareRetrievalRouter()
        self._unified_memory_service = unified_memory_service

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
                if self._unified_memory_service is not None:
                    memory_purpose = (
                        MemoryQueryPurpose.COMPANION
                        if decision.mode is SupportMode.LISTEN
                        else MemoryQueryPurpose.PLANNING
                    )
                    bundle = self._unified_memory_service.search_context(
                        owner_id=request.user_id,
                        query=request.message,
                        purpose=memory_purpose,
                        explicit_personal_recall=any(
                            marker in request.message
                            for marker in self._sensitive_memory_markers
                        ),
                        broad_recall=any(
                            marker in request.message
                            for marker in self._broad_memory_markers
                        ),
                    )
                    memories = MemoryContext(
                        facts=tuple(
                            MemoryItem(
                                item.id,
                                item.content,
                                item.type.value,
                                bundle.relevance.get(item.id),
                                item.confidence.value,
                                item.origin.value,
                                item.updated_at.isoformat(),
                            )
                            for item in bundle.records
                            if item.type is not MemoryType.PREFERENCE
                        ),
                        preferences=tuple(
                            MemoryItem(
                                item.id,
                                item.content,
                                item.type.value,
                                bundle.relevance.get(item.id),
                                item.confidence.value,
                                item.origin.value,
                                item.updated_at.isoformat(),
                            )
                            for item in bundle.records
                            if item.type is MemoryType.PREFERENCE
                        ),
                    )
                    self._unified_memory_service.record_context_usage(
                        request.user_id,
                        bundle.records,
                        turn_id=request.conversation_id,
                        purpose=memory_purpose,
                    )
                else:
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
            except (MemoryStoreError, Exception):
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
