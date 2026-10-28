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


@pytest.mark.asyncio
async def test_explicit_preparation_search_saves_url_backed_sources_for_the_library(
    tmp_path: Path,
) -> None:
    provider = RecordingSearchProvider()
    provider_result = WebSearchResponse(
        answer="找到一份官方学习资料。",
        sources=(
            WebSearchSource(
                "https://example.com/course",
                "AI 产品课程",
                site_name="Example University",
                snippet="一份面向产品岗位的 AI 实践课程。",
            ),
            WebSearchSource("javascript:alert(1)", "不安全链接"),
        ),
        strategy=SearchStrategy.TURBO,
    )

    async def search(query: str, strategy: SearchStrategy) -> WebSearchResponse:
        provider.calls.append((query, strategy))
        return provider_result

    provider.search = search  # type: ignore[method-assign]
    store = SqliteRagStore(tmp_path / "rag.db")
    tool = build_agentic_rag_tool(store, provider, user_id="u1")

    await tool.ainvoke(
        {
            "query": "收集最新的 AI 产品学习资料",
            "scopes": ["preparation"],
            "requires_freshness": True,
            "save_to_library": True,
        }
    )

    saved = store.list_documents_for_domains(("preparation_material",))
    assert len(saved) == 1
    assert saved[0]["title"] == "AI 产品课程"
    assert saved[0]["source_uri"] == "https://example.com/course"
