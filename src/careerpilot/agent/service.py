from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.tools import BaseTool

from careerpilot.agent.base import AgentResponder
from careerpilot.agent.prompt import PromptComposer
from careerpilot.context.contracts import RetrievalSource, TaskIntent
from careerpilot.harness.context import CareerContextCompiler, ContextRequest
from careerpilot.harness.memory import MemoryLifecycle
from careerpilot.memory.base import MemoryStore
from careerpilot.memory.dreaming import (
    CognitiveStore,
    DreamingTriggerPolicy,
)
from careerpilot.memory.write_policy import MemoryWritePolicy
from careerpilot.memory.service import MemoryService
from careerpilot.support.policy import SupportMode, SupportPolicy


@dataclass(frozen=True, slots=True)
class ChatCommand:
    user_id: str
    conversation_id: str
    message: str
    requested_mode: SupportMode | None = None


@dataclass(frozen=True, slots=True)
class ChatResult:
    reply: str
    support_mode: SupportMode
    primary_intent: TaskIntent
    retrieval_sources: tuple[RetrievalSource, ...]
    memory_read_status: str
    memory_write_status: str
    dreaming_status: str


class AgentService:
    def __init__(
        self,
        memory_store: MemoryStore,
        agent: AgentResponder,
        support_policy: SupportPolicy,
        prompt_composer: PromptComposer | None = None,
        memory_write_policy: MemoryWritePolicy | None = None,
        rag_tool_factory: Callable[[str], BaseTool] | None = None,
        action_tool_factory: Callable[[str], tuple[BaseTool, ...]] | None = None,
        cognitive_store: CognitiveStore | None = None,
        dreaming_trigger_policy: DreamingTriggerPolicy | None = None,
        unified_memory_service: MemoryService | None = None,
    ) -> None:
        self._agent = agent
        self._rag_tool_factory = rag_tool_factory
        self._action_tool_factory = action_tool_factory
        self._context_compiler = CareerContextCompiler(
            memory_store,
            support_policy,
            prompt_composer or PromptComposer(),
            cognitive_store,
            unified_memory_service=unified_memory_service,
        )
        self._memory_lifecycle = MemoryLifecycle(
            memory_store,
            memory_write_policy or MemoryWritePolicy(),
            cognitive_store,
            dreaming_trigger_policy or DreamingTriggerPolicy(),
        )

    async def chat(self, command: ChatCommand) -> ChatResult:
        context = await self._context_compiler.compile(
            ContextRequest(
                user_id=command.user_id,
                conversation_id=command.conversation_id,
                message=command.message,
                requested_mode=command.requested_mode,
            )
        )
        allowed_tool_names = set(context.allowed_tool_names)
        runtime_tools: list[BaseTool] = []
        if (
            "search_career_knowledge" in allowed_tool_names
            and self._rag_tool_factory is not None
        ):
            runtime_tools.append(self._rag_tool_factory(command.user_id))
        if (
            context.decision.mode is not SupportMode.LISTEN
            and self._action_tool_factory is not None
        ):
            action_tools = self._action_tool_factory(command.user_id)
            runtime_tools.extend(action_tools)
            allowed_tool_names.update(tool.name for tool in action_tools)
        reply = await self._agent.respond(
            command.message,
            context.system_prompt,
            command.conversation_id,
            allowed_tool_names=frozenset(allowed_tool_names),
            runtime_tools=tuple(runtime_tools),
        )
        memory_result = await self._memory_lifecycle.commit_turn(
            user_id=command.user_id,
            conversation_id=command.conversation_id,
            user_message=command.message,
            assistant_message=reply,
            memories=context.memories,
        )

        return ChatResult(
            reply=reply,
            support_mode=context.decision.mode,
            primary_intent=context.intent.primary_intent,
            retrieval_sources=tuple(
                route.source for route in context.retrieval_plan.routes
            ),
            memory_read_status=context.memory_read_status,
            memory_write_status=memory_result.write_status,
            dreaming_status=memory_result.consolidation_status,
        )
