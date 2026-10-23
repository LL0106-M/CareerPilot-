from pathlib import Path

from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.evidence import build_evidence_units
from careerpilot.rag.models import EvidenceKind, SourceDocument
from careerpilot.rag.retrieval import QueryPlan, QueryPlanner, RagRetriever
from careerpilot.rag.store import SqliteRagStore


class FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        return [
            float("ai" in lowered or "agent" in lowered or "产品" in text),
            float("访谈" in text or "用户研究" in text),
            float("国企" in text or "稳定" in text),
        ]


class CountingEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        self.query_calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        return super().embed_query(text)


def _upsert(store: SqliteRagStore, document: SourceDocument) -> None:
    chunks = chunk_document(document)
    store.upsert(document, chunks, build_evidence_units(document, chunks))


def test_query_planner_normalizes_without_keyword_routing() -> None:
    plan = QueryPlanner().plan(
        " AI 产品经理需要哪些能力？ ",
        domain="job_opportunity",
        sub_queries=("技术能力", "产品能力"),
        requires_freshness=True,
    )

    assert plan.domain == "job_opportunity"
    assert plan.queries == ("AI 产品经理需要哪些能力", "技术能力", "产品能力")
    assert plan.requires_freshness is True
    assert plan.max_rounds == 2


def test_retriever_hybrid_fuses_sparse_dense_triple_and_graph(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db", embedder=FakeEmbedder())
    document = SourceDocument(
        "job-1",
        "AI Agent 产品经理",
        "https://example.com/job",
        "company_official",
        "preparation_material",
        "AI 产品经理需要用户研究能力，也需要访谈经历。",
        metadata={
            "source_tier": 1,
            "triples": [
                {"subject": "AI产品经理", "relation": "需要", "object": "用户研究能力"},
                {"subject": "用户研究能力", "relation": "可迁移自", "object": "访谈经历"},
            ],
        },
    )
    _upsert(store, document)

    result = RagRetriever(store).retrieve(
        "AI 产品经理需要哪些能力", domain="preparation_material", limit=8
    )

    assert result.hits
    assert any("dense" in hit.channels for hit in result.hits)
    assert any(hit.evidence_kind is EvidenceKind.KG_TRIPLE for hit in result.hits)
    assert any("graph" in hit.channels and "访谈经历" in hit.content for hit in result.hits)
    assert len({hit.evidence_id for hit in result.hits}) == len(result.hits)
    assert result.stop_reason == "enough"


def test_retriever_reuses_one_query_embedding_for_passages_and_triples(tmp_path: Path) -> None:
    embedder = CountingEmbedder()
    store = SqliteRagStore(tmp_path / "rag.db", embedder=embedder)
    document = SourceDocument(
        "prep-query-cache",
        "用户研究能力",
        "file:///prep-query-cache.md",
        "developer_upload",
        "preparation_material",
        "用户研究能力通过访谈经历体现。",
        metadata={
            "triples": [
                {"subject": "用户研究能力", "relation": "通过", "object": "访谈经历"}
            ]
        },
    )
    _upsert(store, document)
    embedder.query_calls = 0

    RagRetriever(store).retrieve(
        "用户研究能力如何关联访谈经历",
        domain="preparation_material",
        use_graph=True,
    )

    assert embedder.query_calls == 1


def test_job_retrieval_does_not_use_graph_evidence(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "job-no-graph",
        "AI 产品岗位",
        "https://example.com/job",
        "web_job",
        "job_opportunity",
        "AI 产品经理需要用户研究能力。",
        metadata={
            "triples": [
                {"subject": "AI产品经理", "relation": "需要", "object": "用户研究能力"}
            ]
        },
    )
    _upsert(store, document)

    result = RagRetriever(store).retrieve(
        "AI 产品经理需要什么能力", domain="job_opportunity", limit=5
    )

    assert result.hits
    assert all(hit.evidence_kind is not EvidenceKind.KG_TRIPLE for hit in result.hits)
    assert all("graph" not in hit.channels for hit in result.hits)


def test_retriever_respects_explicit_domain_filter(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    job = SourceDocument(
        "job-1",
        "Agent 产品经理",
        "https://example.com/job",
        "web_job",
        "job_opportunity",
        "任职要求：熟悉 RAG、Memory、工具调用与 Agent 效果评测。",
    )
    article = SourceDocument(
        "article-1",
        "Agent Memory 技术文章",
        "https://example.com/article",
        "web_article",
        "ai_frontier",
        "本文介绍 Memory 和 RAG 的技术原理。",
    )
    _upsert(store, job)
    _upsert(store, article)

    result = RagRetriever(store).retrieve(
        "Agent 产品经理岗位要求", domain="job_opportunity"
    )

    assert result.hits
    assert {hit.domain for hit in result.hits} == {"job_opportunity"}


def test_retriever_ranks_child_and_returns_parent_context(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "prep-parent",
        "需求分析面试准备",
        "file:///prep.md",
        "developer_upload",
        "preparation_material",
        "# 需求分析\n\n先识别用户问题。再验证需求优先级。最后形成可验证方案并复盘。",
    )
    _upsert(store, document)

    result = RagRetriever(store).retrieve(
        "如何验证需求优先级", domain="preparation_material", limit=3
    )

    assert result.hits
    hit = result.hits[0]
    assert "用户问题" in hit.content
    assert "复盘" in hit.content
    assert "需求优先级" in hit.metadata["matched_content"]
    assert hit.metadata["context_chunk_level"] == "parent"
    assert hit.metadata["matched_chunk_id"] != hit.metadata["context_chunk_id"]


def test_retriever_marks_multi_source_synthesis_partial(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    job = SourceDocument(
        "job-1",
        "Agent 产品经理",
        "https://example.com/job",
        "web_job",
        "job_opportunity",
        "岗位职责和任职要求包括 Agent、RAG 与产品设计。",
    )
    _upsert(store, job)
    planner = QueryPlanner(default_minimum_sources=2)

    result = RagRetriever(store, planner=planner).retrieve("Agent 产品经理普遍需要哪些能力")

    assert result.status == "partial"
    assert result.distinct_sources == 1
    assert result.needs_online_search is True
    assert result.stop_reason == "needs_online_search"


def test_retriever_stops_when_rewrite_adds_no_new_evidence(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "doc",
        "RAG",
        "https://example.com/rag",
        "developer_upload",
        "domain_knowledge",
        "RAG 使用外部证据增强回答。",
    )
    _upsert(store, document)
    plan = QueryPlan(
        domain="domain_knowledge",
        validation_target="cross_source_synthesis",
        queries=("RAG 外部证据",),
        minimum_sources=2,
        requires_freshness=False,
        max_rounds=2,
    )

    class FixedPlanner:
        def plan(self, query: str, **kwargs) -> QueryPlan:
            return plan

    def repeat_query(plan: QueryPlan, round_number: int) -> tuple[str, ...]:
        return plan.queries

    result = RagRetriever(
        store,
        planner=FixedPlanner(),
        query_rewriter=repeat_query,
    ).retrieve("RAG 外部证据")

    assert result.rounds == 2
    assert result.stop_reason == "no_new_evidence"
    assert len(result.clues) == 1
