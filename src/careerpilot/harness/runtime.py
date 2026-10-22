from dataclasses import dataclass, field

from careerpilot.harness.contracts import HarnessMessage, ModelGateway, ModelRequest
from careerpilot.harness.session import InMemorySessionStore
from careerpilot.harness.tools import ToolPolicy, ToolRegistry


class MaxStepsExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HarnessRunResult:
    reply: str
    steps: int
    tool_names: tuple[str, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)


class CareerPilotHarness:
    """Provider-neutral model/tool loop owned by CareerPilot."""

    def __init__(
        self,
        model: ModelGateway,
        tools: ToolRegistry | None = None,
        session_store=None,
        *,
        max_steps: int = 4,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self._model = model
        self._tools = tools or ToolRegistry()
        self._sessions = session_store or InMemorySessionStore()
        self._max_steps = max_steps

    async def run(
        self,
        *,
        user_message: str,
        system_context: str,
        session_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools=(),
    ) -> HarnessRunResult:
        history = await self._sessions.load(session_id)
        turn: list[HarnessMessage] = [HarnessMessage(role="user", content=user_message)]
        registry = self._tools.overlay(tuple(runtime_tools))
        policy = ToolPolicy(allowed_tool_names)
        tool_names: list[str] = []
        usage: dict[str, int] = {}

        for step in range(1, self._max_steps + 1):
            response = await self._model.generate(
                ModelRequest(
                    messages=(
                        HarnessMessage(role="system", content=system_context),
                        *history,
                        *turn,
                    ),
                    tools=registry.schemas(policy),
                )
            )
            for key, value in response.usage.items():
                usage[key] = usage.get(key, 0) + value
            assistant = HarnessMessage(
                role="assistant",
                content=response.text,
                tool_calls=response.tool_calls,
            )
            turn.append(assistant)
            if not response.tool_calls:
                if not response.text:
                    raise RuntimeError("Model returned neither text nor tool calls")
                await self._sessions.append(session_id, tuple(turn))
                return HarnessRunResult(
                    reply=response.text,
                    steps=step,
                    tool_names=tuple(tool_names),
                    usage=usage,
                )

            for call in response.tool_calls:
                tool_names.append(call.name)
                result = await registry.execute(call.name, call.arguments, policy)
                turn.append(
                    HarnessMessage(
                        role="tool",
                        content=result,
                        tool_call_id=call.id,
                        name=call.name,
                    )
                )

        await self._sessions.append(session_id, tuple(turn))
        raise MaxStepsExceeded(f"Agent exceeded {self._max_steps} model steps")
