from pathlib import Path

from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.evidence import build_evidence_units
from careerpilot.rag.models import ChunkLevel, DocumentChunk, EvidenceKind, SourceDocument
from careerpilot.rag.store import SqliteRagStore


class FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        if "国央企" in text or "国企" in text:
            return [0.0, 1.0]
        return [1.0, 0.0]


class FailingEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding service unavailable")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("embedding service unavailable")


def test_store_indexes_and_returns_cited_chunks(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    job = SourceDocument(
        id="didi-agent-pm",
        title="滴滴 AI Agent 产品经理",
        source_uri="https://talent.didiglobal.com/social/p/63915",
        source_type="web_job",
        domain="job_opportunity",
        text="负责 Agent 工具调用、上下文、Memory、任务编排和效果评测体系。",
        metadata={"organization": "滴滴", "location": "北京"},
    )
    graph = SourceDocument(
        id="graphrag-guide",
        title="知识图谱提取与图 RAG 检索",
        source_uri="file:///KG_Extractor%26GraphRAG.pdf",
        source_type="developer_upload",
        domain="ai_frontier",
        text="生产形态是混合工作流，原文是最终证据，图是证据的索引。",
    )
    store.upsert(job, chunk_document(job))
    store.upsert(graph, chunk_document(graph))

    hits = store.search("Agent 产品经理需要哪些能力", domain="job_opportunity", limit=3)

    assert hits
    assert hits[0].document_id == "didi-agent-pm"
    assert hits[0].source_uri == "https://talent.didiglobal.com/social/p/63915"
    assert hits[0].metadata["organization"] == "滴滴"
    assert all(hit.domain == "job_opportunity" for hit in hits)


def test_upsert_replaces_old_document_chunks(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    old = SourceDocument("doc", "旧版", "file:///doc", "upload", "ai_frontier", "旧版本内容")
    new = SourceDocument("doc", "新版", "file:///doc", "upload", "ai_frontier", "新版新增 GraphRAG")

    store.upsert(old, chunk_document(old))
    store.upsert(new, chunk_document(new))

    assert store.search("旧版本内容") == ()
    assert store.search("GraphRAG")[0].title == "新版"


def test_store_expands_matched_child_to_parent_context(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "doc-parent",
        "面试准备",
        "file:///interview.md",
        "developer_upload",
        "preparation_material",
        "# 需求分析\n\n先识别用户问题。再验证需求优先级。最后形成可验证方案。",
    )
    chunks = chunk_document(
        document,
        max_chars=20,
        overlap_chars=3,
        parent_max_chars=80,
    )
    store.upsert(document, chunks)

    child_hit = store.search_sparse("需求优先级", limit=1)[0]
    expanded = store.expand_parent_context((child_hit,))[0]

    assert expanded.parent_id is not None
    assert "用户问题" in expanded.content
    assert "可验证方案" in expanded.content
    assert "需求优先级" in expanded.metadata["matched_content"]
    assert expanded.metadata["context_chunk_level"] == ChunkLevel.PARENT.value


def test_store_indexes_passage_triple_and_table_row_in_one_collection(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "doc-1",
        "岗位样本",
        "https://example.com/jobs",
        "developer_upload",
        "preparation_material",
        "AI产品经理岗位说明。",
        metadata={
            "triples": [
                {"subject": "AI产品经理", "relation": "需要", "object": "用户研究能力"}
            ],
            "table_name": "jobs",
            "table_rows": [
                {"row_id": "job-1", "values": {"职位": "AI产品经理", "城市": "上海"}}
            ],
        },
    )
    chunks = chunk_document(document)
    store.upsert(document, chunks, build_evidence_units(document, chunks))

    triple_hits = store.search_sparse(
        "用户研究能力", kinds=frozenset({EvidenceKind.KG_TRIPLE}), limit=5
    )
    row_hits = store.search_sparse(
        "上海", kinds=frozenset({EvidenceKind.TABLE_ROW}), limit=5
    )

    assert triple_hits[0].evidence_kind is EvidenceKind.KG_TRIPLE
    assert row_hits[0].evidence_kind is EvidenceKind.TABLE_ROW
    assert store.count_evidence() == 8


def test_images_are_registered_without_search_evidence(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "doc-images",
        "带图资料",
        "file:///guide.pdf",
        "developer_upload",
        "preparation_material",
        "正文只介绍需求分析。",
        metadata={
            "images": [
                {
                    "image_id": "image-1",
                    "page_number": 2,
                    "object_uri": "s3://careerpilot/images/image-1.png",
                    "image_type": "diagram",
                    "bbox": [10, 20, 300, 400],
                    "caption": "独特流程图说明",
                }
            ]
        },
    )

    store.upsert(document, chunk_document(document))

    assert store.count_image_assets() == 1
    assert store.search_sparse("独特流程图说明") == ()


def test_dense_search_uses_optional_embedder(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db", embedder=FakeEmbedder())
    ai = SourceDocument(
        "ai",
        "AI产品岗位",
        "https://example.com/ai",
        "web_job",
        "job_opportunity",
        "AI产品经理负责智能体产品设计。",
    )
    soe = SourceDocument(
        "soe",
        "国央企岗位",
        "https://example.com/soe",
        "web_job",
        "job_opportunity",
        "国央企通过校园招聘吸纳毕业生。",
    )
    store.upsert(ai, chunk_document(ai))
    store.upsert(soe, chunk_document(soe))

    hits = store.search_dense("国央企招聘", limit=2)

    assert hits[0].document_id == "soe"
    assert "dense" in hits[0].channels
    assert store.count_sparse_entries() == store.count_evidence()
    assert store.count_dense_vectors() == store.count_evidence()


def test_structured_job_search_returns_api_object_evidence(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    store.upsert_job(
        {
            "id": "job-1",
            "company_name": "示例科技",
            "role_title": "AI 产品经理",
            "role_family": "ai_product",
            "recruiting_type": "campus",
            "organization_type": "private",
            "employment_type": "enterprise_contract",
            "locations_json": '["北京"]',
            "deadline": "2026-12-31",
            "apply_url": "https://example.com/apply",
            "source_url": "https://example.com/job",
            "source_level": "S",
            "source_name": "官网",
            "posted_at": "2026-10-01",
            "verified_at": "2026-10-23",
            "job_description": "负责智能体产品设计。",
            "requirements": "具备用户研究能力。",
            "status": "active",
            "knowledge_origin": "system_web",
            "owner_user_id": None,
        }
    )

    hits = store.search_job_records("北京 AI 产品经理岗位")

    assert hits[0].evidence_kind is EvidenceKind.API_OBJECT
    assert hits[0].channels == ("structured",)
    assert hits[0].metadata["apply_url"] == "https://example.com/apply"


def test_graph_neighbors_only_use_provenanced_triples(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "doc-graph",
        "能力关系",
        "https://example.com/graph",
        "developer_upload",
        "domain_knowledge",
        "岗位能力关系。",
        metadata={
            "triples": [
                {"subject": "AI产品经理", "relation": "需要", "object": "用户研究能力"},
                {"subject": "用户研究能力", "relation": "可迁移自", "object": "访谈经历"},
            ]
        },
    )
    chunks = chunk_document(document)
    store.upsert(document, chunks, build_evidence_units(document, chunks))
    seed = store.search_sparse(
        "AI产品经理 用户研究能力",
        kinds=frozenset({EvidenceKind.KG_TRIPLE}),
        limit=1,
    )[0]

    neighbors = store.neighbors((seed.evidence_id,), limit=5)

    assert any("访谈经历" in hit.content for hit in neighbors)
    assert all(hit.source_uri for hit in neighbors)


def test_hipporag_index_builds_passage_phrase_graph_and_ppr_crosses_passages(
    tmp_path: Path,
) -> None:
    store = SqliteRagStore(tmp_path / "rag.db", embedder=FakeEmbedder())
    document = SourceDocument(
        "doc-hippo",
        "产品能力关系",
        "file:///hippo.md",
        "developer_upload",
        "preparation_material",
        "AI产品经理需要用户研究能力。用户研究能力可通过访谈经历证明。",
        metadata={
            "triples": [
                {
                    "subject": "AI产品经理",
                    "relation": "需要",
                    "object": "用户研究能力",
                    "chunk_ordinal": 0,
                },
                {
                    "subject": "用户研究能力",
                    "relation": "可通过",
                    "object": "访谈经历",
                    "chunk_ordinal": 1,
                },
            ]
        },
    )
    chunks = (
        DocumentChunk(
            "chunk-ai",
            document.id,
            0,
            document.title,
            "岗位能力",
            "AI产品经理需要用户研究能力。",
            document.source_uri,
            document.source_type,
            document.domain,
        ),
        DocumentChunk(
            "chunk-interview",
            document.id,
            1,
            document.title,
            "经历证明",
            "用户研究能力可通过访谈经历证明。",
            document.source_uri,
            document.source_type,
            document.domain,
        ),
    )
    store.upsert(document, chunks, build_evidence_units(document, chunks))

    assert store.count_graph_nodes(node_type="passage") == 2
    assert store.count_graph_nodes(node_type="phrase") == 3
    assert store.count_graph_edges(edge_type="contains") == 4
    assert store.count_graph_edges(edge_type="relation") == 2

    seed = store.search_dense(
        "AI产品经理",
        kinds=frozenset({EvidenceKind.KG_TRIPLE}),
        limit=1,
    )
    hits = store.search_graph_ppr(seed, domain="preparation_material", limit=5)

    assert any(hit.chunk_id == "chunk-ai" for hit in hits)
    assert any(hit.chunk_id == "chunk-interview" for hit in hits)
    assert all("ppr" in hit.channels for hit in hits)
    assert store.index_health()["ready"] is True


def test_embedding_failure_degrades_to_sparse_search(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db", embedder=FailingEmbedder())
    document = SourceDocument(
        "doc",
        "RAG 原理",
        "https://example.com/rag",
        "developer_upload",
        "domain_knowledge",
        "RAG 使用检索证据增强生成。",
    )
    store.upsert(document, chunk_document(document))

    assert store.search_dense("RAG") == ()
    assert store.search_sparse("RAG")


def test_strict_dense_indexing_rolls_back_before_replacing_document(tmp_path: Path) -> None:
    database = tmp_path / "rag.db"
    original = SourceDocument(
        "doc",
        "RAG 原理",
        "https://example.com/rag",
        "developer_upload",
        "domain_knowledge",
        "旧版本保留稀疏检索。",
    )
    healthy_store = SqliteRagStore(database, embedder=FakeEmbedder())
    healthy_store.upsert(original, chunk_document(original))
    healthy_store.close()

    replacement = SourceDocument(
        "doc",
        "RAG 新版",
        "https://example.com/rag",
        "developer_upload",
        "domain_knowledge",
        "新版内容不能形成向量。",
    )
    strict_store = SqliteRagStore(
        database,
        embedder=FailingEmbedder(),
        strict_embeddings=True,
    )

    try:
        strict_store.upsert(replacement, chunk_document(replacement))
    except RuntimeError as exc:
        assert "dense indexing failed" in str(exc)
    else:
        raise AssertionError("strict dense indexing should fail")

    assert strict_store.search_sparse("旧版本保留")
    assert strict_store.search_sparse("新版内容") == ()
