from __future__ import annotations

import json
import sys

import pytest
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from careerpilot.harness.tools import ToolPolicy, ToolRegistry
from careerpilot.mcp.adapter import McpToolAdapter
from careerpilot.mcp.client import OfficialMcpClient
from careerpilot.mcp.models import McpServerConfig
from careerpilot.mcp.policy import McpToolPolicy


def _config() -> McpServerConfig:
    return McpServerConfig.model_validate(
        {
            "name": "career-data",
            "transport": "stdio",
            "command": sys.executable,
            "allowed_tools": ["read_resume"],
        }
    )


def _server() -> MCPServer:
    server = MCPServer("Career data")

    @server.tool(
        description="Read an approved resume",
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    )
    def read_resume(resume_id: str) -> dict[str, str]:
        return {"resume_id": resume_id, "summary": "Backend engineer"}

    return server


@pytest.mark.asyncio
async def test_adapter_preserves_schema_and_invokes_original_tool_name() -> None:
    config = _config()
    client = OfficialMcpClient(config, target=_server())
    descriptor = (await client.list_tools())[0]
    tool = McpToolAdapter(descriptor, client, McpToolPolicy((config,))).as_langchain_tool()

    payload = json.loads(await tool.ainvoke({"resume_id": "resume-7"}))

    assert tool.name == "mcp__career_data__read_resume"
    assert isinstance(tool.args_schema, dict)
    assert tool.args_schema["required"] == ["resume_id"]
    assert payload["status"] == "completed"
    assert payload["content_is_untrusted"] is True
    assert payload["structured_content"]["resume_id"] == "resume-7"

    registry_schema = ToolRegistry.from_langchain((tool,)).schemas(ToolPolicy())[0]
    assert registry_schema.parameters["required"] == ["resume_id"]


@pytest.mark.asyncio
async def test_adapter_rechecks_policy_before_execution() -> None:
    config = _config()
    client = OfficialMcpClient(config, target=_server())
    descriptor = (await client.list_tools())[0]
    denied = McpToolPolicy(
        (config,), denied_names=frozenset({descriptor.namespaced_name})
    )
    tool = McpToolAdapter(descriptor, client, denied).as_langchain_tool()

    payload = json.loads(await tool.ainvoke({"resume_id": "resume-7"}))

    assert payload == {
        "status": "forbidden",
        "content_is_untrusted": True,
        "server": "career_data",
        "tool": "read_resume",
    }
