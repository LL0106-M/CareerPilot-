from datetime import UTC, datetime
from pathlib import Path

from careerpilot.ingestion.pipeline import JobIngestionPipeline
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.store import SqliteRagStore


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "company_name": "示例公司",
        "role_title": "Agent 产品经理",
        "locations": ["北京"],
        "source_url": "https://jobs.example.com/agent-pm?utm_source=feed",
        "apply_url": "https://jobs.example.com/agent-pm/apply",
        "source_level": "S",
        "status": "active",
        "requirements": "熟悉 RAG、Memory 和 Agent 评测",
    }
    record.update(overrides)
    return record


def _pipeline(tmp_path: Path) -> tuple[SqliteRagStore, JobIngestionPipeline]:
    store = SqliteRagStore(tmp_path / "rag.db")
    return store, JobIngestionPipeline(store, RagIndexer(store))


def test_pipeline_indexes_job_and_registers_source(tmp_path: Path) -> None:
    store, pipeline = _pipeline(tmp_path)
    fetched_at = datetime(2026, 10, 20, 12, tzinfo=UTC)

    result = pipeline.run([_record()], fetched_at=fetched_at)

    assert result.discovered == 1
    assert result.indexed == 1
    assert result.unchanged == 0
    assert result.rejected == 0
    assert store.count_documents() == 1
    assert store.count_evidence() > 1
    assert store.source_content_hash("https://jobs.example.com/agent-pm") is not None
    assert store.due_sources(now=fetched_at) == ()


def test_pipeline_skips_unchanged_source_without_reindexing(tmp_path: Path) -> None:
    store, pipeline = _pipeline(tmp_path)
    fetched_at = datetime(2026, 10, 20, 12, tzinfo=UTC)
    pipeline.run([_record()], fetched_at=fetched_at)
    evidence_count = store.count_evidence()

    result = pipeline.run(
        [_record()],
        fetched_at=datetime(2026, 10, 21, 12, tzinfo=UTC),
    )

    assert result.indexed == 0
    assert result.unchanged == 1
    assert store.count_evidence() == evidence_count


def test_pipeline_deduplicates_batch_and_reports_invalid_records(tmp_path: Path) -> None:
    store, pipeline = _pipeline(tmp_path)
    fetched_at = datetime(2026, 10, 20, 12, tzinfo=UTC)

    result = pipeline.run(
        [_record(), _record(source_url="https://jobs.example.com/agent-pm?from=search"), {}],
        fetched_at=fetched_at,
    )

    assert result.discovered == 3
    assert result.indexed == 1
    assert result.duplicates == 1
    assert result.rejected == 1
    assert result.errors[0].startswith("record 3:")
    assert store.count_documents() == 1
