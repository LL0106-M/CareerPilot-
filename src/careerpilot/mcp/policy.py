from __future__ import annotations

from collections.abc import Iterable

from careerpilot.mcp.models import McpServerConfig, McpToolDescriptor


class McpToolPolicy:
    """Fail-closed policy for model-visible MCP tools."""

    def __init__(
        self,
        servers: Iterable[McpServerConfig],
        *,
        denied_names: frozenset[str] = frozenset(),
    ) -> None:
        self._servers = {server.name: server for server in servers}
        self._denied_names = denied_names

    def allows(self, descriptor: McpToolDescriptor) -> bool:
        server = self._servers.get(descriptor.server_name)
        if server is None or not server.enabled:
            return False
        if (
            descriptor.server_fingerprint
            and descriptor.server_fingerprint != server.fingerprint
        ):
            return False
        if descriptor.namespaced_name in self._denied_names:
            return False
        if server.allowed_tools is not None and descriptor.tool_name not in server.allowed_tools:
            return False
        return descriptor.read_only is True and descriptor.destructive is not True
