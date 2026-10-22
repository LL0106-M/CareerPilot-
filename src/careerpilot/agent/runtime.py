from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from careerpilot.agent.base import AgentResponder
from careerpilot.harness.model import LangChainModelGateway
from careerpilot.harness.runtime import CareerPilotHarness
from careerpilot.harness.session import InMemorySessionStore
from careerpilot.harness.tools import ToolRegistry


class CareerPilotResponder(AgentResponder):
    """Adapter from the application service to the CareerPilot-owned harness."""

    def __init__(
        self,
        model: BaseChatModel,
        tools: list[BaseTool] | None = None,
        *,
        session_store=None,
        max_steps: int = 4,
    ) -> None:
        registry = ToolRegistry.from_langchain(tuple(tools or ()))
        self._harness = CareerPilotHarness(
            LangChainModelGateway(model),
            registry,
            session_store or InMemorySessionStore(),
            max_steps=max_steps,
        )

    async def respond(
        self,
        user_message: str,
        system_context: str,
        thread_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools: tuple[BaseTool, ...] = (),
    ) -> str:
        result = await self._harness.run(
            user_message=user_message,
            system_context=system_context,
            session_id=thread_id,
            allowed_tool_names=allowed_tool_names,
            runtime_tools=runtime_tools,
        )
        return result.reply
