import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from careerpilot.config import Settings
from careerpilot.mcp.config import load_mcp_servers
from careerpilot.mcp.models import McpServerConfig


def test_missing_mcp_config_disables_servers(tmp_path: Path) -> None:
    assert load_mcp_servers(tmp_path / "missing.json") == ()


def test_loads_stdio_and_streamable_http_servers(tmp_path: Path) -> None:
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "Local Files",
                        "description": "Read approved resume files",
                        "transport": "stdio",
                        "command": "python",
                        "args": ["resume_server.py"],
                        "env": {"CAREERPILOT_SCOPE": "resumes"},
                        "allowed_tools": ["read_resume"],
                    },
                    {
                        "name": "Career Search",
                        "description": "Search public career sources",
                        "transport": "streamable_http",
                        "url": "https://search.example.com/mcp",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    servers = load_mcp_servers(config_path)

    assert [server.name for server in servers] == ["local_files", "career_search"]
    assert servers[0].command == "python"
    assert servers[0].args == ("resume_server.py",)
    assert servers[0].env == {"CAREERPILOT_SCOPE": "resumes"}
    assert servers[0].allowed_tools == frozenset({"read_resume"})
    assert servers[1].url == "https://search.example.com/mcp"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"name": "files", "transport": "stdio"}, "command"),
        (
            {
                "name": "search",
                "transport": "streamable_http",
                "url": "http://search.example.com/mcp",
            },
            "HTTPS",
        ),
        (
            {
                "name": "search",
                "transport": "streamable_http",
                "url": "https://search.example.com/mcp",
                "command": "python",
            },
            "command",
        ),
    ],
)
def test_transport_specific_configuration_fails_closed(
    payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        McpServerConfig.model_validate(payload)


def test_loopback_http_is_allowed_for_local_development() -> None:
    server = McpServerConfig.model_validate(
        {
            "name": "local-search",
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8090/mcp",
        }
    )

    assert server.name == "local_search"
    assert server.url == "http://127.0.0.1:8090/mcp"


def test_settings_exposes_optional_mcp_config_path(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "mcp.json"
    monkeypatch.setenv("CAREERPILOT_MCP_CONFIG_PATH", str(config_path))

    settings = Settings(_env_file=None)

    assert settings.mcp_config_path == config_path
