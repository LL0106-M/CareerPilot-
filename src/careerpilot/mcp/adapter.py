from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from careerpilot.harness.contracts import HarnessTool, ToolSchema
from careerpilot.harness.tools import FunctionHarnessTool
from careerpilot.mcp.client import McpClientProtocol
from careerpilot.mcp.models import McpToolDescriptor
from careerpilot.mcp.policy import McpToolPolicy


class McpToolAdapter:
    """Expose one selected MCP tool through the existing runtime overlay."""

    def __init__(
        self,
        descriptor: McpToolDescriptor,
        client: McpClientProtocol,
        policy: McpToolPolicy,
    ) -> None:
        self._descriptor = descriptor
        self._client = client
        self._policy = policy

    def as_harness_tool(self) -> HarnessTool:
        async def invoke(**arguments: Any) -> str:
            descriptor = self._descriptor
            if not self._policy.allows(descriptor):
                return json.dumps(
                    {
                        "status": "forbidden",
                        "content_is_untrusted": True,
                        "server": descriptor.server_name,
                        "tool": descriptor.tool_name,
                    },
                    ensure_ascii=False,
                )
            result = await self._client.call_tool(descriptor.tool_name, arguments)
            payload = asdict(result)
            payload["server"] = payload.pop("server_name")
            payload["tool"] = payload.pop("tool_name")
            payload["content_is_untrusted"] = True
            return json.dumps(payload, ensure_ascii=False, default=str)

        return FunctionHarnessTool(
            ToolSchema(
                name=self._descriptor.namespaced_name,
                description=self._descriptor.description,
                parameters=self._descriptor.input_schema,
            ),
            invoke,
        )
