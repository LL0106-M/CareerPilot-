import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from careerpilot.rag.store import SqliteRagStore
from careerpilot.rag.tool import build_agentic_rag_tool
from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource


@dataclass
class RecordingSearchProvider:
    calls: list[tuple[str, SearchStrategy]] = field(default_factory=list)

    async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse:
        self.calls.append((query, strategy))
        return WebSearchResponse(
            answer="找到一条官方岗位。",
            sources=(WebSearchSource("https://example.com/job", "官方岗位"),),
            strategy=strategy,
        )


@pytest.mark.asyncio
async def test_agentic_tool_performs_online_fallback_inside_rag_backend(tmp_path: Path) -> None:
    provider = RecordingSearchProvider()
    tool = build_agentic_rag_tool(SqliteRagStore(tmp_path / "rag.db"), provider)

    raw = await tool.ainvoke(
        {
            "query": "最近的 AI 产品岗位",
            "scopes": ["jobs"],
            "requires_freshness": True,
        }
    )
    result = json.loads(raw)

    assert tool.name == "search_career_knowledge"
    assert provider.calls == [("最近的 AI 产品岗位", SearchStrategy.TURBO)]
    assert result["status"] == "available"
    assert result["retrieval"]["used_online_search"] is True
    assert result["retrieval"]["stop_reason"] == "online_evidence"
    assert result["online_sources"][0]["url"] == "https://example.com/job"
    assert result["needs_ingestion"] is True
    assert "query_plan" not in result


@pytest.mark.asyncio
async def test_agentic_tool_rejects_personal_scope_without_bound_user(tmp_path: Path) -> None:
    tool = build_agentic_rag_tool(SqliteRagStore(tmp_path / "rag.db"), None)

    raw = await tool.ainvoke({"query": "我的项目经历", "scopes": ["personal"]})
    result = json.loads(raw)

    assert result["status"] == "forbidden"
    assert result["error"] == "personal_scope_requires_authenticated_user"
