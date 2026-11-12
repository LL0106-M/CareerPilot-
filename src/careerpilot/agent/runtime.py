from collections.abc import AsyncIterator

from careerpilot.agent.base import AgentResponder, AgentResponse
from careerpilot.harness.contracts import HarnessTool, ModelGateway
from careerpilot.harness.events import HarnessEvent
from careerpilot.harness.run_store import SqliteAgentRunStore
from careerpilot.harness.runtime import CareerPilotHarness
from careerpilot.harness.session import InMemorySessionStore
from careerpilot.harness.tools import ToolRegistry


class CareerPilotResponder(AgentResponder):
    """Adapter from the application service to the CareerPilot-owned harness."""

    def __init__(
        self,
        model: ModelGateway,
        tools: list[HarnessTool] | None = None,
        *,
        session_store=None,
        max_steps: int = 4,
        run_store: SqliteAgentRunStore | None = None,
    ) -> None:
        registry = ToolRegistry(tuple(tools or ()))
        self._harness = CareerPilotHarness(
            model,
            registry,
            session_store or InMemorySessionStore(),
            max_steps=max_steps,
            run_store=run_store,
        )

    async def respond(
        self,
        user_message: str,
        system_context: str,
        thread_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools: tuple[HarnessTool, ...] = (),
        run_id: str | None = None,
    ) -> AgentResponse:
        result = await self._harness.run(
            user_message=user_message,
            system_context=system_context,
            session_id=thread_id,
            allowed_tool_names=allowed_tool_names,
            runtime_tools=runtime_tools,
            run_id=run_id,
        )
        return AgentResponse(
            reply=result.reply,
            run_id=result.run_id,
            citation_ids=result.citation_ids,
            citation_warnings=result.citation_warnings,
        )

    async def stream(
        self,
        user_message: str,
        system_context: str,
        thread_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools: tuple[HarnessTool, ...] = (),
        run_id: str | None = None,
    ) -> AsyncIterator[HarnessEvent]:
        async for event in self._harness.stream(
            user_message=user_message,
            system_context=system_context,
            session_id=thread_id,
            allowed_tool_names=allowed_tool_names,
            runtime_tools=runtime_tools,
            run_id=run_id,
        ):
            yield event
