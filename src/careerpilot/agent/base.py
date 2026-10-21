from typing import Protocol

from langchain_core.tools import BaseTool


class AgentResponder(Protocol):
    async def respond(
        self,
        user_message: str,
        system_context: str,
        thread_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools: tuple[BaseTool, ...] = (),
    ) -> str: ...
