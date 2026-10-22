from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HarnessMessage:
    role: str
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: tuple[HarnessMessage, ...]
    tools: tuple[ToolSchema, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelStreamEvent:
    """One provider-neutral item from a streaming model invocation."""

    text_delta: str = ""
    response: ModelResponse | None = None


class ModelGateway(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...


class SessionStore(Protocol):
    async def load(self, session_id: str) -> tuple[HarnessMessage, ...]: ...

    async def append(
        self, session_id: str, messages: tuple[HarnessMessage, ...]
    ) -> None: ...


class HarnessTool(Protocol):
    @property
    def schema(self) -> ToolSchema: ...

    async def execute(self, arguments: dict[str, Any]) -> str: ...
