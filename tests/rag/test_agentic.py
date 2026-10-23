from dataclasses import dataclass, field
from pathlib import Path

import pytest

from careerpilot.rag.agentic import (
    AgenticRagOrchestrator,
    AgenticRetrievalRequest,
    KnowledgeScope,
)
from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.models import KnowledgeOrigin, SourceDocument
from careerpilot.rag.store import SqliteRagStore
from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource


@dataclass
class RecordingWebSearch:
    responses: list[WebSearchResponse]
    calls: list[tuple[str, SearchStrategy]] = field(default_factory=list)

    async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse:
        self.calls.append((query, strategy))
        return self.responses.pop(0)


def _index(store: SqliteRagStore, document: SourceDocument) -> None:
    store.upsert(document, chunk_document(document))


@pytest.mark.asyncio
async def test_agentic_rag_stops_when_local_evidence_is_sufficient(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    _index(
        store,
        SourceDocument(
            id="prep-1",
            title="Agent 面试准备",
            source_uri="https://example.com/prep",
            source_type="developer_upload",
            domain="curated_document",
            text="Agent 产品面试需要准备 RAG 评测、工具调用和安全边界。",
            knowledge_origin=KnowledgeOrigin.SYSTEM_CURATED,
        ),
    )
    web = RecordingWebSearch([])
    orchestrator = AgenticRagOrchestrator(store, web_search=web)

    result = await orchestrator.retrieve(
        AgenticRetrievalRequest(
            query="Agent 产品面试需要准备什么",
            scopes=(KnowledgeScope.PREPARATION,),
        )
    )

    assert result.status == "available"
    assert result.hits
    assert result.online_sources == ()
    assert web.calls == []
    assert result.trace.stop_reason == "enough"


@pytest.mark.asyncio
async def test_agentic_rag_searches_online_when_local_evidence_is_insufficient(
    tmp_path: Path,
) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    web = RecordingWebSearch(
        [
            WebSearchResponse(
                answer="发现新的官方招聘公告。",
                sources=(
                    WebSearchSource(
                        url="https://company.example/jobs/agent-pm",
                        title="Agent 产品经理招聘",
                        site_name="公司招聘官网",
                    ),
                ),
                strategy=SearchStrategy.TURBO,
                request_id="req-1",
            )
        ]
    )
    orchestrator = AgenticRagOrchestrator(store, web_search=web)

    result = await orchestrator.retrieve(
        AgenticRetrievalRequest(
            query="最近开放的 Agent 产品经理岗位",
            scopes=(KnowledgeScope.JOBS,),
            requires_freshness=True,
        )
    )

    assert web.calls == [("最近开放的 Agent 产品经理岗位", SearchStrategy.TURBO)]
    assert result.status == "available"
    assert result.online_sources[0].url == "https://company.example/jobs/agent-pm"
    assert result.needs_ingestion is True
    assert result.trace.used_online_search is True
    assert result.trace.stop_reason == "online_evidence"
    assert result.trace.local_rounds == 0
    assert result.trace.retrieval_mode.value == "web_only"
    assert result.hits == ()


@pytest.mark.asyncio
async def test_agentic_rag_escalates_search_only_when_turbo_is_still_insufficient(
    tmp_path: Path,
) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    web = RecordingWebSearch(
        [
            WebSearchResponse(
                answer="没有可靠来源。",
                sources=(),
                strategy=SearchStrategy.TURBO,
                partial=True,
            ),
            WebSearchResponse(
                answer="找到两份可核验资料。",
                sources=(
                    WebSearchSource("https://a.example/prep", "资料 A"),
                    WebSearchSource("https://b.example/prep", "资料 B"),
                ),
                strategy=SearchStrategy.MAX,
            ),
        ]
    )
    orchestrator = AgenticRagOrchestrator(store, web_search=web)

    result = await orchestrator.retrieve(
        AgenticRetrievalRequest(
            query="事业单位产品岗备考资料",
            scopes=(KnowledgeScope.PREPARATION,),
            minimum_sources=2,
        )
    )

    assert web.calls == [
        ("事业单位产品岗备考资料", SearchStrategy.TURBO),
        ("事业单位产品岗备考资料", SearchStrategy.MAX),
    ]
    assert result.status == "available"
    assert len(result.online_sources) == 2
    assert result.trace.online_rounds == 2


def test_user_provided_material_is_visible_only_to_its_owner(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    _index(
        store,
        SourceDocument(
            id="user-prep-1",
            title="我的面试笔记",
            source_uri="user-upload://user-1/note.txt",
            source_type="user_upload",
            domain="curated_document",
            text="面试时重点讲述供应链项目的跨部门推进。",
            knowledge_origin=KnowledgeOrigin.USER_PROVIDED,
            owner_user_id="user-1",
        ),
    )

    owner_hits = store.search_sparse("供应链项目", user_id="user-1")
    other_hits = store.search_sparse("供应链项目", user_id="user-2")
    anonymous_hits = store.search_sparse("供应链项目")

    assert owner_hits and owner_hits[0].knowledge_origin is KnowledgeOrigin.USER_PROVIDED
    assert other_hits == ()
    assert anonymous_hits == ()


def test_user_provided_material_requires_an_owner() -> None:
    with pytest.raises(ValueError, match="owner_user_id"):
        SourceDocument(
            id="invalid",
            title="无主资料",
            source_uri="user-upload://invalid",
            source_type="user_upload",
            domain="curated_document",
            text="内容",
            knowledge_origin=KnowledgeOrigin.USER_PROVIDED,
        )
