import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from careerpilot.harness.contracts import HarnessTool, ToolSchema


class ToolExecutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    allowed_names: frozenset[str] | None = None

    def allows(self, name: str) -> bool:
        return self.allowed_names is None or name in self.allowed_names


class FunctionHarnessTool(HarnessTool):
    """A small native tool wrapper for synchronous or asynchronous handlers."""

    def __init__(
        self,
        schema: ToolSchema,
        handler: Callable[..., object],
    ) -> None:
        self._schema = schema
        self._handler = handler

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            result = self._handler(**arguments)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            raise ToolExecutionError(f"Tool {self.schema.name} failed") from exc
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)


class ToolRegistry:
    def __init__(self, tools: tuple[HarnessTool, ...] = ()) -> None:
        self._tools: dict[str, HarnessTool] = {}
        for tool in tools:
            name = tool.schema.name
            if name in self._tools:
                raise ValueError(f"Duplicate tool name: {name}")
            self._tools[name] = tool

    def overlay(self, tools: tuple[HarnessTool, ...]) -> "ToolRegistry":
        duplicates = self._tools.keys() & {tool.schema.name for tool in tools}
        if duplicates:
            name = sorted(duplicates)[0]
            raise ValueError(f"Duplicate tool name: {name}")
        return ToolRegistry((*self._tools.values(), *tools))

    def schemas(self, policy: ToolPolicy) -> tuple[ToolSchema, ...]:
        return tuple(
            tool.schema for name, tool in self._tools.items() if policy.allows(name)
        )

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        policy: ToolPolicy,
    ) -> str:
        if not policy.allows(name):
            return json.dumps({"status": "forbidden", "tool": name}, ensure_ascii=False)
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"status": "not_found", "tool": name}, ensure_ascii=False)
        try:
            return await tool.execute(arguments)
        except ToolExecutionError as exc:
            return json.dumps(
                {"status": "failed", "tool": name, "error": str(exc)}, ensure_ascii=False
            )
