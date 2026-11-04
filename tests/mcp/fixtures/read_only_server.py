from __future__ import annotations

import os

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

mcp = MCPServer("CareerPilot test server")


@mcp.tool(
    description="Inspect the explicitly provided fixture environment",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
)
def inspect_fixture_environment() -> dict[str, object]:
    return {
        "explicit": os.environ.get("CAREERPILOT_FIXTURE_SCOPE"),
        "unrelated_secret_present": "CAREERPILOT_UNRELATED_SECRET" in os.environ,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
