from __future__ import annotations

from dataclasses import replace

import pytest

from careerpilot.mcp.client import McpConnectionError
from careerpilot.mcp.models import McpServerConfig, McpToolDescriptor, McpToolResult
from careerpilot.mcp.platform import McpToolPlatform


def _server(name: str, *, enabled: bool = True) -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": name,
            "transport": "stdio",
            "command": "python",
            "enabled": enabled,
        }
    )


def _descriptor(
    server: McpServerConfig,
    name: str,
    description: str,
    *,
    read_only: bool | None = True,
) -> McpToolDescriptor:
    return McpToolDescriptor(
        server_name=server.name,
        tool_name=name,
        description=description,
        input_schema={"type": "object", "properties": {}},
        read_only=read_only,
        destructive=False,
        server_fingerprint=server.fingerprint,
    )


class StaticClient:
    def __init__(
        self,
        tools: tuple[McpToolDescriptor, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self.tools = tools
        self.error = error

    async def list_tools(
        self, *, force_refresh: bool = False
    ) -> tuple[McpToolDescriptor, ...]:
        if self.error is not None:
            raise self.error
        return self.tools

    async def call_tool(self, name: str, arguments: dict) -> McpToolResult:
        return McpToolResult("completed", self.tools[0].server_name, name)


@pytest.mark.asyncio
async def test_platform_keeps_healthy_servers_and_filters_unknown_risk() -> None:
    search = _server("search")
    records = _server("records")
    search_tool = _descriptor(search, "search_jobs", "Search current job listings")
    unknown_risk = _descriptor(records, "read_record", "Read a record", read_only=None)
    platform = McpToolPlatform(
        (search, records),
        clients={
            search.name: StaticClient((search_tool,)),
            records.name: StaticClient(
                (unknown_risk,), McpConnectionError("records unavailable")
            ),
        },
    )

    tools = await platform.runtime_tools("owner-1", "search current jobs")

    assert [tool.name for tool in tools] == ["mcp__search__search_jobs"]


@pytest.mark.asyncio
async def test_platform_caps_selection_and_rejects_stale_fingerprints() -> None:
    server = _server("career")
    descriptors = tuple(
        _descriptor(server, f"search_jobs_{index}", "Search jobs")
        for index in range(12)
    )
    stale = replace(descriptors[0], server_fingerprint="stale")
    platform = McpToolPlatform(
        (server,), clients={server.name: StaticClient((stale, *descriptors[1:]))}
    )

    tools = await platform.runtime_tools("owner-1", "search jobs")

    assert len(tools) == 8
    assert "mcp__career__search_jobs_0" not in {tool.name for tool in tools}


@pytest.mark.asyncio
async def test_platform_returns_no_tools_for_unrelated_query_or_disabled_server() -> None:
    server = _server("calendar", enabled=False)
    descriptor = _descriptor(server, "read_calendar", "Read calendar events")
    platform = McpToolPlatform(
        (server,), clients={server.name: StaticClient((descriptor,))}
    )

    assert await platform.runtime_tools("owner-1", "review my resume") == ()
    assert await platform.visible_tools() == ()
