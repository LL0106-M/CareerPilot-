from dataclasses import dataclass
from typing import Protocol

from careerpilot.harness.contracts import HarnessTool


@dataclass(frozen=True, slots=True)
class AgentResponse:
    reply: str
    run_id: str
    citation_ids: tuple[str, ...] = ()
    citation_warnings: tuple[str, ...] = ()


class AgentResponder(Protocol):
    async def respond(
        self,
        user_message: str,
        system_context: str,
        thread_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools: tuple[HarnessTool, ...] = (),
        run_id: str | None = None,
    ) -> AgentResponse: ...
