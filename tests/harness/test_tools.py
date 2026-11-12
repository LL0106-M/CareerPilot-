import json

import pytest

from careerpilot.harness.contracts import ToolSchema
from careerpilot.harness.tools import (
    FunctionHarnessTool,
    ToolExecutionError,
    ToolPolicy,
    ToolRegistry,
)


def _schema(name: str = "lookup") -> ToolSchema:
    return ToolSchema(
        name=name,
        description="Look something up",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )


@pytest.mark.asyncio
async def test_function_tool_runs_sync_handler_and_preserves_string() -> None:
    tool = FunctionHarnessTool(_schema(), lambda query: f"result:{query}")

    assert await tool.execute({"query": "career"}) == "result:career"
    assert tool.schema == _schema()


@pytest.mark.asyncio
async def test_function_tool_runs_async_handler_and_serializes_json() -> None:
    async def lookup(query: str) -> dict[str, object]:
        return {"query": query, "items": [1, 2]}

    tool = FunctionHarnessTool(_schema(), lookup)

    assert json.loads(await tool.execute({"query": "career"})) == {
        "query": "career",
        "items": [1, 2],
    }


@pytest.mark.asyncio
async def test_function_tool_sanitizes_handler_error() -> None:
    def fail(query: str) -> None:
        raise RuntimeError(f"secret for {query}")

    tool = FunctionHarnessTool(_schema(), fail)

    with pytest.raises(ToolExecutionError, match="Tool lookup failed") as captured:
        await tool.execute({"query": "private"})
    assert "secret" not in str(captured.value)
    assert isinstance(captured.value.__cause__, RuntimeError)


def test_registry_rejects_duplicate_names_in_constructor_and_overlay() -> None:
    first = FunctionHarnessTool(_schema(), lambda query: query)
    duplicate = FunctionHarnessTool(_schema(), lambda query: query)

    with pytest.raises(ValueError, match="Duplicate tool name: lookup"):
        ToolRegistry((first, duplicate))

    registry = ToolRegistry((first,))
    with pytest.raises(ValueError, match="Duplicate tool name: lookup"):
        registry.overlay((duplicate,))


@pytest.mark.asyncio
async def test_registry_applies_policy_and_handles_not_found_and_failures() -> None:
    def fail(query: str) -> None:
        raise RuntimeError(query)

    registry = ToolRegistry((FunctionHarnessTool(_schema(), fail),))

    forbidden = json.loads(
        await registry.execute("lookup", {"query": "x"}, ToolPolicy(frozenset()))
    )
    missing = json.loads(
        await registry.execute("missing", {}, ToolPolicy(frozenset({"missing"})))
    )
    failed = json.loads(
        await registry.execute("lookup", {"query": "x"}, ToolPolicy())
    )

    assert forbidden == {"status": "forbidden", "tool": "lookup"}
    assert missing == {"status": "not_found", "tool": "missing"}
    assert failed == {
        "status": "failed",
        "tool": "lookup",
        "error": "Tool lookup failed",
    }
