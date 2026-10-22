import json
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool

from careerpilot.harness.contracts import HarnessTool, ToolSchema


class ToolExecutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    allowed_names: frozenset[str] | None = None

    def allows(self, name: str) -> bool:
        return self.allowed_names is None or name in self.allowed_names


class LangChainToolAdapter(HarnessTool):
    """Keep existing RAG tools usable without giving LangChain control of the loop."""

    def __init__(self, tool: BaseTool) -> None:
        self._tool = tool
        input_schema = tool.get_input_schema()
        self._schema = ToolSchema(
            name=tool.name,
            description=tool.description,
            parameters=input_schema.model_json_schema(),
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            result = await self._tool.ainvoke(arguments)
        except Exception as exc:
            raise ToolExecutionError(f"Tool {self.schema.name} failed") from exc
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)


class ToolRegistry:
    def __init__(self, tools: tuple[HarnessTool, ...] = ()) -> None:
        self._tools = {tool.schema.name: tool for tool in tools}

    @classmethod
    def from_langchain(cls, tools: tuple[BaseTool, ...]) -> "ToolRegistry":
        return cls(tuple(LangChainToolAdapter(tool) for tool in tools))

    def overlay(self, tools: tuple[BaseTool, ...]) -> "ToolRegistry":
        combined = dict(self._tools)
        for tool in tools:
            adapter = LangChainToolAdapter(tool)
            combined[adapter.schema.name] = adapter
        return ToolRegistry(tuple(combined.values()))

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
