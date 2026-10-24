import json
from pathlib import Path

import pytest

from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.models import SourceDocument
from careerpilot.rag.store import SqliteRagStore
from careerpilot.rag.tool import build_rag_tool


@pytest.mark.asyncio
async def test_rag_tool_returns_citations_and_untrusted_context(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "job-1",
        "Agent 产品经理",
        "https://example.com/job",
        "web_job",
        "job_opportunity",
        "负责 RAG、Memory、工具调用与任务评测。",
        {"organization": "示例公司"},
    )
    store.upsert(document, chunk_document(document))
    tool = build_rag_tool(store)

    raw = await tool.ainvoke(
        {
            "query": "Agent 产品经理 Memory",
            "domain": "job_opportunity",
            "validation_target": "job_requirements",
        }
    )
    result = json.loads(raw)

    assert tool.name == "search_career_knowledge"
    assert result["status"] == "available"
    assert result["content_is_untrusted"] is True
    assert result["hits"][0]["source_uri"] == "https://example.com/job"
    assert result["query_plan"]["validation_target"] == "job_requirements"
    assert result["evidence"]["distinct_sources"] == 1
    assert result["evidence"]["stop_reason"] == "enough"
    assert result["hits"][0]["channels"] == ["sparse"]
    assert result["hits"][0]["evidence_kind"] == "passage"


@pytest.mark.asyncio
async def test_rag_tool_reports_insufficient_without_fabricating(tmp_path: Path) -> None:
    tool = build_rag_tool(SqliteRagStore(tmp_path / "rag.db"))

    raw = await tool.ainvoke({"query": "不存在的知识", "domain": None})
    result = json.loads(raw)

    assert result["status"] == "insufficient"
    assert result["content_is_untrusted"] is True
    assert result["query_plan"] == {
            "domain": None,
            "validation_target": "direct_fact",
            "queries": ["不存在的知识"],
            "minimum_sources": 1,
            "requires_freshness": False,
            "max_rounds": 2,
        }
    assert result["evidence"] == {
            "distinct_sources": 0,
            "needs_online_search": True,
            "rounds": 1,
            "stop_reason": "needs_online_search",
            "clues": [],
        }
    assert result["hits"] == []
    assert result["context_pack"]["evidence"] == []
    assert result["context_pack"]["relation_clues"] == []
