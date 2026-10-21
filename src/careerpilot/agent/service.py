from dataclasses import dataclass
from collections.abc import Callable

from langchain_core.tools import BaseTool

from careerpilot.agent.base import AgentResponder
from careerpilot.agent.prompt import PromptComposer
from careerpilot.memory.base import MemoryContext, MemoryStore, MemoryStoreError
from careerpilot.memory.write_policy import MemoryWritePolicy
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
    memory_read_status: str
    memory_write_status: str


class AgentService:
    def __init__(
        self,
        memory_store: MemoryStore,
        agent: AgentResponder,
        support_policy: SupportPolicy,
        prompt_composer: PromptComposer | None = None,
        memory_write_policy: MemoryWritePolicy | None = None,
        rag_tool_factory: Callable[[str], BaseTool] | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._agent = agent
        self._support_policy = support_policy
        self._prompt_composer = prompt_composer or PromptComposer()
        self._memory_write_policy = memory_write_policy or MemoryWritePolicy()
        self._rag_tool_factory = rag_tool_factory

    async def chat(self, command: ChatCommand) -> ChatResult:
        decision = self._support_policy.decide(command.message, command.requested_mode)
        memory_read_status = "available"
        try:
            memories = await self._memory_store.search(
                command.user_id,
                command.conversation_id,
                command.message,
            )
        except MemoryStoreError:
            memories = MemoryContext()
            memory_read_status = "unavailable"

        system_context = self._prompt_composer.compose(decision, memories)
        allowed_tool_names = (
            frozenset()
            if decision.mode is SupportMode.LISTEN
            else frozenset({"search_career_knowledge"})
        )
        runtime_tools = (
            ()
            if decision.mode is SupportMode.LISTEN or self._rag_tool_factory is None
            else (self._rag_tool_factory(command.user_id),)
        )
        reply = await self._agent.respond(
            command.message,
            system_context,
            command.conversation_id,
            allowed_tool_names=allowed_tool_names,
            runtime_tools=runtime_tools,
        )

        memory_write_status = "skipped"
        if self._memory_write_policy.should_write(command.message):
            memory_write_status = "accepted"
            try:
                await self._memory_store.add_turn(
                    command.user_id,
                    command.conversation_id,
                    command.message,
                    reply,
                )
            except MemoryStoreError:
                memory_write_status = "unavailable"

        return ChatResult(
            reply=reply,
            support_mode=decision.mode,
            memory_read_status=memory_read_status,
            memory_write_status=memory_write_status,
        )
