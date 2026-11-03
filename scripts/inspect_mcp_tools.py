from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from careerpilot.mcp.config import load_mcp_servers
from careerpilot.mcp.platform import McpToolPlatform


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List policy-visible MCP tools without invoking them."
    )
    parser.add_argument("--config", required=True, type=Path)
    return parser


async def _inspect(config_path: Path) -> dict[str, object]:
    servers = load_mcp_servers(config_path)
    if not servers:
        raise ValueError("No MCP servers are configured")
    tools = await McpToolPlatform(servers).visible_tools(
        force_refresh=True,
        strict_connections=True,
    )
    return {
        "server_count": len(servers),
        "visible_tool_count": len(tools),
        "tools": [
            {
                "name": tool.namespaced_name,
                "server": tool.server_name,
                "tool": tool.tool_name,
                "description": tool.description,
                "read_only": tool.read_only,
                "destructive": tool.destructive,
                "input_schema": tool.input_schema,
            }
            for tool in tools
        ],
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        payload = asyncio.run(_inspect(args.config))
    except Exception as exc:
        print(
            f"MCP inspection failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
