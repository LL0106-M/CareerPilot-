from pathlib import Path

from careerpilot.api.dependencies import build_agent_tools, build_mcp_tool_factory
from careerpilot.config import Settings
from careerpilot.rag.store import SqliteRagStore


def test_agent_tools_omit_web_search_without_dashscope_credentials(tmp_path: Path) -> None:
    tools = build_agent_tools(Settings(_env_file=None), SqliteRagStore(tmp_path / "rag.db"))

    assert [tool.name for tool in tools] == ["search_career_knowledge"]


def test_agent_tools_register_web_search_when_dashscope_is_configured(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "secret")
    monkeypatch.setenv(
        "CAREERPILOT_DASHSCOPE_BASE_URL",
        "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
    )

    tools = build_agent_tools(Settings(_env_file=None), SqliteRagStore(tmp_path / "rag.db"))

    assert [tool.name for tool in tools] == ["search_career_knowledge"]
    assert "bounded online fallback" in tools[0].description


def test_mcp_factory_is_enabled_only_when_a_server_config_exists(
    tmp_path: Path,
) -> None:
    assert build_mcp_tool_factory(Settings(_env_file=None)) is None
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        '{"servers":[{"name":"local","transport":"stdio",'
        '"command":"python","enabled":true}]}',
        encoding="utf-8",
    )

    factory = build_mcp_tool_factory(
        Settings(_env_file=None, CAREERPILOT_MCP_CONFIG_PATH=config_path)
    )

    assert callable(factory)
