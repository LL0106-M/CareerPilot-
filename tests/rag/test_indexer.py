from pathlib import Path
from typing import Any

from careerpilot.rag.extraction import _sample_evenly
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.models import DocumentChunk, SourceDocument
from careerpilot.rag.store import SqliteRagStore


def test_indexer_ingests_markdown_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "job.md").write_text(
        """---
document_id: job-1
content_type: job_opportunity
source_type: web_job
title: Agent 产品经理
canonical_url: https://example.com/job
---
# Agent 产品经理
负责 RAG、Memory 与工具调用。
""",
        encoding="utf-8",
    )
    store = SqliteRagStore(tmp_path / "rag.db")

    result = RagIndexer(store).ingest_markdown_directory(source_dir)

    assert result.documents == 1
    assert result.chunks == 1
    assert store.search("Memory 工具调用")[0].document_id == "job-1"


class _GraphExtractor:
    def extract(
        self, document: SourceDocument, chunks: tuple[DocumentChunk, ...]
    ) -> list[dict[str, Any]]:
        child = next(chunk for chunk in chunks if chunk.chunk_level.value == "child")
        return [
            {
                "subject": "RAG",
                "predicate": "使用",
                "object": "向量检索",
                "evidence_quote": "RAG 使用向量检索",
                "chunk_ordinal": child.ordinal,
            }
        ]


def test_indexer_runs_graph_extraction_only_for_curated_professional_knowledge(
    tmp_path: Path,
) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        id="knowledge-1",
        title="RAG",
        source_uri="file:///knowledge.md",
        source_type="developer_upload",
        domain="preparation_material",
        text="# RAG\n\nRAG 使用向量检索。",
    )

    result = RagIndexer(store, graph_extractor=_GraphExtractor()).ingest_document(document)

    assert result.graph_relations == 1
    assert store.search("向量检索")[0].document_id == "knowledge-1"


def test_graph_smoke_sampling_spans_the_document() -> None:
    chunks = tuple(
        DocumentChunk(
            id=f"chunk-{index}",
            document_id="doc",
            ordinal=index,
            title="title",
            heading="heading",
            content="content",
            source_uri="file:///doc.md",
            source_type="developer_upload",
            domain="preparation_material",
        )
        for index in range(12)
    )

    sampled = _sample_evenly(chunks, 3)

    assert [chunk.ordinal for chunk in sampled] == [3, 6, 9]
