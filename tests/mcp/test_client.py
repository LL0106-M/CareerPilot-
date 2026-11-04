from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from careerpilot.mcp.client import OfficialMcpClient
from careerpilot.mcp.models import McpServerConfig


def _config(**overrides: object) -> McpServerConfig:
    payload: dict[str, object] = {
        "name": "career-data",
        "description": "Career records and resumes",
        "transport": "stdio",
        "command": sys.executable,
    }
    payload.update(overrides)
    return McpServerConfig.model_validate(payload)


def _server() -> MCPServer:
    server = MCPServer("Career data")

    @server.tool(
        title="Resume reader",
        description="Read an approved resume",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    )
    def read_resume(resume_id: str) -> dict[str, str]:
        return {"resume_id": resume_id, "summary": "Python engineer"}

    @server.tool(
        description="Return plain text",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
        structured_output=False,
    )
    def read_note() -> list[TextContent]:
        return [TextContent(type="text", text="interview note")]

    @server.tool(
        description="Fail safely",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    )
    def failing_read() -> str:
        raise RuntimeError("SECRET_SHOULD_NOT_ESCAPE")

    return server


@pytest.mark.asyncio
async def test_real_sdk_client_discovers_annotations_and_calls_structured_tool() -> None:
    client = OfficialMcpClient(_config(), target=_server())

    descriptors = await client.list_tools()
    result = await client.call_tool("read_resume", {"resume_id": "resume-1"})

    descriptor = next(item for item in descriptors if item.tool_name == "read_resume")
    assert descriptor.namespaced_name == "mcp__career_data__read_resume"
    assert descriptor.title == "Resume reader"
    assert descriptor.read_only is True
    assert descriptor.destructive is False
    assert descriptor.input_schema["required"] == ["resume_id"]
    assert result.status == "completed"
    assert result.structured_content == {
        "resume_id": "resume-1",
        "summary": "Python engineer",
    }


@pytest.mark.asyncio
async def test_client_uses_text_fallback_and_sanitizes_tool_failure() -> None:
    client = OfficialMcpClient(_config(), target=_server())

    text_result = await client.call_tool("read_note", {})
    failed_result = await client.call_tool("failing_read", {})

    assert text_result.status == "completed"
    assert text_result.text_content == ("interview note",)
    assert failed_result.status == "failed"
    assert failed_result.error == "remote_tool_error"
    assert "SECRET_SHOULD_NOT_ESCAPE" not in repr(failed_result)


@pytest.mark.asyncio
async def test_descriptor_cache_requires_refresh_to_observe_new_tool() -> None:
    server = _server()
    client = OfficialMcpClient(_config(), target=server)
    first = await client.list_tools()

    @server.tool(
        description="Search jobs",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    )
    def search_jobs(query: str) -> dict[str, str]:
        return {"query": query}

    cached = await client.list_tools()
    refreshed = await client.list_tools(force_refresh=True)

    assert {item.tool_name for item in cached} == {item.tool_name for item in first}
    assert "search_jobs" in {item.tool_name for item in refreshed}


@pytest.mark.asyncio
async def test_client_bounds_oversized_structured_result() -> None:
    server = MCPServer("Large result")

    @server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    )
    def read_large_record() -> dict[str, str]:
        return {"content": "x" * 2_000}

    client = OfficialMcpClient(_config(max_result_chars=256), target=server)

    result = await client.call_tool("read_large_record", {})

    assert result.status == "completed"
    assert result.truncated is True
    assert result.structured_content is None
    assert len(result.text_content[0]) <= 256


@pytest.mark.asyncio
async def test_client_prefers_structured_content_over_duplicate_text() -> None:
    server = MCPServer("Mixed result")

    @server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    )
    def read_mixed_record() -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text="x" * 180)],
            structuredContent={"content": "y" * 180},
        )

    client = OfficialMcpClient(_config(max_result_chars=256), target=server)

    result = await client.call_tool("read_mixed_record", {})

    assert result.structured_content == {"content": "y" * 180}
    assert result.text_content == ()
    assert result.truncated is False


@pytest.mark.asyncio
async def test_stdio_client_does_not_forward_unrelated_host_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "read_only_server.py"
    monkeypatch.setenv("CAREERPILOT_UNRELATED_SECRET", "do-not-forward")
    config = _config(
        name="stdio-fixture",
        args=[str(fixture)],
        env={"CAREERPILOT_FIXTURE_SCOPE": "resumes"},
    )
    client = OfficialMcpClient(config)

    descriptors = await client.list_tools()
    result = await client.call_tool("inspect_fixture_environment", {})

    assert [item.tool_name for item in descriptors] == ["inspect_fixture_environment"]
    assert result.structured_content == {
        "explicit": "resumes",
        "unrelated_secret_present": False,
    }
