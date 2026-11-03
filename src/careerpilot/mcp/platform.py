from __future__ import annotations

import asyncio
from collections.abc import Mapping

from langchain_core.tools import BaseTool

from careerpilot.mcp.adapter import McpToolAdapter
from careerpilot.mcp.catalog import McpToolCatalog
from careerpilot.mcp.client import (
    McpClientProtocol,
    McpConnectionError,
    OfficialMcpClient,
)
from careerpilot.mcp.models import McpServerConfig, McpToolDescriptor
from careerpilot.mcp.policy import McpToolPolicy


class McpDiscoveryError(RuntimeError):
    """A sanitized MCP platform error safe for application-level degradation."""


class McpToolPlatform:
    """Discover, filter, and select a bounded MCP tool overlay for one turn."""

    def __init__(
        self,
        servers: tuple[McpServerConfig, ...],
        *,
        clients: Mapping[str, McpClientProtocol] | None = None,
        max_tools: int = 8,
        max_concurrency: int = 4,
    ) -> None:
        self._servers = tuple(server for server in servers if server.enabled)
        provided = dict(clients or {})
        self._clients: dict[str, McpClientProtocol] = {
            server.name: provided.get(server.name) or OfficialMcpClient(server)
            for server in self._servers
        }
        self._policy = McpToolPolicy(self._servers)
        self._catalog = McpToolCatalog()
        self._max_tools = max(0, min(max_tools, 8))
        self._max_concurrency = max(1, max_concurrency)

    async def visible_tools(
        self, *, force_refresh: bool = False
    ) -> tuple[McpToolDescriptor, ...]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def discover(
            server: McpServerConfig,
        ) -> tuple[McpToolDescriptor, ...] | Exception:
            try:
                async with semaphore:
                    return await self._clients[server.name].list_tools(
                        force_refresh=force_refresh
                    )
            except Exception as exc:
                return exc

        discoveries = await asyncio.gather(
            *(discover(server) for server in self._servers)
        )
        visible: list[McpToolDescriptor] = []
        for discovery in discoveries:
            if isinstance(discovery, McpConnectionError):
                continue
            if isinstance(discovery, Exception):
                raise McpDiscoveryError(
                    f"MCP discovery failed ({type(discovery).__name__})"
                ) from None
            visible.extend(
                descriptor
                for descriptor in discovery
                if self._policy.allows(descriptor)
            )
        return tuple(sorted(visible, key=lambda item: item.namespaced_name))

    async def runtime_tools(
        self, owner_id: str, query: str
    ) -> tuple[BaseTool, ...]:
        del owner_id  # Reserved for future owner-scoped authorization.
        descriptors = await self.visible_tools()
        selected = self._catalog.select(
            query, descriptors, limit=self._max_tools
        )
        return tuple(
            McpToolAdapter(
                descriptor,
                self._clients[descriptor.server_name],
                self._policy,
            ).as_langchain_tool()
            for descriptor in selected
        )
