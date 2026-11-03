from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from careerpilot.mcp.models import McpServerConfig


class _McpConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servers: tuple[McpServerConfig, ...] = ()


def load_mcp_servers(path: Path | str | None) -> tuple[McpServerConfig, ...]:
    """Load a fail-closed MCP server file; an absent path disables MCP."""

    if path is None:
        return ()
    config_path = Path(path)
    if not config_path.is_file():
        return ()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    document = _McpConfigFile.model_validate(payload)
    names = [server.name for server in document.servers]
    if len(set(names)) != len(names):
        raise ValueError("MCP server names must be unique after normalization")
    return document.servers
