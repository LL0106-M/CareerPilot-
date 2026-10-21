from pathlib import Path

from careerpilot.api.dependencies import build_agent_tools
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
