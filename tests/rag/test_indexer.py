from pathlib import Path

from careerpilot.rag.indexer import RagIndexer
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
