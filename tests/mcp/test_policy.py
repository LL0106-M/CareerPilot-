from careerpilot.mcp.models import McpServerConfig, McpToolDescriptor
from careerpilot.mcp.policy import McpToolPolicy


def _server(**overrides: object) -> McpServerConfig:
    payload: dict[str, object] = {
        "name": "career-data",
        "transport": "stdio",
        "command": "python",
    }
    payload.update(overrides)
    return McpServerConfig.model_validate(payload)


def _tool(**overrides: object) -> McpToolDescriptor:
    payload: dict[str, object] = {
        "server_name": "career_data",
        "tool_name": "read_resume",
        "description": "Read an approved resume",
        "input_schema": {"type": "object", "properties": {}},
        "read_only": True,
        "destructive": False,
    }
    payload.update(overrides)
    return McpToolDescriptor(**payload)


def test_policy_allows_explicit_read_only_non_destructive_tool() -> None:
    assert McpToolPolicy((_server(),)).allows(_tool()) is True


def test_policy_denies_unknown_write_destructive_and_disabled_tools() -> None:
    enabled = McpToolPolicy((_server(),))
    disabled = McpToolPolicy((_server(enabled=False),))

    assert enabled.allows(_tool(read_only=None)) is False
    assert enabled.allows(_tool(read_only=False)) is False
    assert enabled.allows(_tool(destructive=True)) is False
    assert enabled.allows(_tool(read_only=True, destructive=True)) is False
    assert disabled.allows(_tool()) is False


def test_policy_enforces_server_tool_allowlist_and_application_denylist() -> None:
    server = _server(allowed_tools=["search_jobs"])

    assert McpToolPolicy((server,)).allows(_tool(tool_name="read_resume")) is False
    assert (
        McpToolPolicy((server,)).allows(
            _tool(tool_name="search_jobs", description="Search approved jobs")
        )
        is True
    )
    assert (
        McpToolPolicy(
            (server,), denied_names=frozenset({"mcp__career_data__search_jobs"})
        ).allows(_tool(tool_name="search_jobs"))
        is False
    )


def test_policy_denies_descriptor_from_unknown_or_changed_server() -> None:
    server = _server()
    policy = McpToolPolicy((server,))

    assert policy.allows(_tool(server_name="other")) is False
    assert policy.allows(_tool(server_fingerprint="stale")) is False
