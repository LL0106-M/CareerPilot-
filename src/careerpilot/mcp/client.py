from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any, Protocol

from mcp import Client, StdioServerParameters
from mcp.types import TextContent

from careerpilot.mcp.models import McpServerConfig, McpToolDescriptor, McpToolResult


class McpClientProtocol(Protocol):
    async def list_tools(
        self, *, force_refresh: bool = False
    ) -> tuple[McpToolDescriptor, ...]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult: ...


class McpConnectionError(RuntimeError):
    pass


class OfficialMcpClient:
    """Small fail-safe wrapper around the official MCP SDK v2 client."""

    def __init__(
        self,
        config: McpServerConfig,
        *,
        target: object | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._target = target if target is not None else _target_from_config(config)
        self._clock = clock
        self._cached_tools: tuple[McpToolDescriptor, ...] | None = None
        self._cached_at = 0.0

    async def list_tools(
        self, *, force_refresh: bool = False
    ) -> tuple[McpToolDescriptor, ...]:
        if (
            not force_refresh
            and self._cached_tools is not None
            and self._clock() - self._cached_at < self.config.descriptor_ttl_seconds
        ):
            return self._cached_tools

        descriptors: list[McpToolDescriptor] = []
        seen_names: set[str] = set()
        try:
            async with Client(
                self._target,
                read_timeout_seconds=self.config.timeout_seconds,
            ) as client:
                cursor: str | None = None
                while True:
                    page = await client.list_tools(cursor=cursor)
                    for tool in page.tools:
                        descriptor = _normalize_tool(self.config, tool)
                        if descriptor is None or descriptor.tool_name in seen_names:
                            continue
                        seen_names.add(descriptor.tool_name)
                        descriptors.append(descriptor)
                    cursor = page.next_cursor
                    if cursor is None:
                        break
        except Exception as exc:
            raise McpConnectionError(
                f"MCP server {self.config.name!r} is unavailable ({type(exc).__name__})"
            ) from None

        self._cached_tools = tuple(descriptors)
        self._cached_at = self._clock()
        return self._cached_tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        try:
            async with Client(
                self._target,
                read_timeout_seconds=self.config.timeout_seconds,
            ) as client:
                result = await client.call_tool(
                    name,
                    arguments,
                    read_timeout_seconds=self.config.timeout_seconds,
                )
        except Exception as exc:
            return McpToolResult(
                status="failed",
                server_name=self.config.name,
                tool_name=name,
                error=f"connection_error:{type(exc).__name__}",
            )

        if result.is_error:
            return McpToolResult(
                status="failed",
                server_name=self.config.name,
                tool_name=name,
                error="remote_tool_error",
            )

        text_content = tuple(
            block.text for block in result.content if isinstance(block, TextContent)
        )
        return _bound_result(
            McpToolResult(
                status="completed",
                server_name=self.config.name,
                tool_name=name,
                structured_content=result.structured_content,
                text_content=text_content,
            ),
            self.config.max_result_chars,
        )


def _target_from_config(config: McpServerConfig) -> object:
    if config.transport == "streamable_http":
        assert config.url is not None
        return config.url
    assert config.command is not None
    return StdioServerParameters(
        command=config.command,
        args=list(config.args),
        env=dict(config.env) or None,
    )


def _normalize_tool(config: McpServerConfig, tool: Any) -> McpToolDescriptor | None:
    name = getattr(tool, "name", None)
    schema = getattr(tool, "input_schema", None)
    if not isinstance(name, str) or not name.strip() or not isinstance(schema, dict):
        return None
    if schema.get("type", "object") != "object":
        return None
    annotations = getattr(tool, "annotations", None)
    return McpToolDescriptor(
        server_name=config.name,
        tool_name=name,
        title=getattr(tool, "title", None),
        description=getattr(tool, "description", None) or "",
        input_schema=schema,
        read_only=(
            getattr(annotations, "read_only_hint", None)
            if annotations is not None
            else None
        ),
        destructive=(
            getattr(annotations, "destructive_hint", None)
            if annotations is not None
            else None
        ),
        server_description=config.description,
        server_fingerprint=config.fingerprint,
    )


def _bound_result(result: McpToolResult, limit: int) -> McpToolResult:
    if result.structured_content is not None:
        serialized = json.dumps(result.structured_content, ensure_ascii=False, default=str)
        if len(serialized) > limit:
            return McpToolResult(
                status=result.status,
                server_name=result.server_name,
                tool_name=result.tool_name,
                text_content=(serialized[:limit],),
                truncated=True,
            )
    joined = "\n".join(result.text_content)
    if len(joined) > limit:
        return McpToolResult(
            status=result.status,
            server_name=result.server_name,
            tool_name=result.tool_name,
            structured_content=result.structured_content,
            text_content=(joined[:limit],),
            truncated=True,
        )
    return result
