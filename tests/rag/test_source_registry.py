from datetime import UTC, datetime
from pathlib import Path

from careerpilot.rag.models import WebSource
from careerpilot.rag.store import SqliteRagStore


def test_source_registry_returns_only_due_active_urls(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    store.register_source(
        WebSource(
            url="https://example.com/jobs",
            source_type="company_job_page",
            domain="job_opportunity",
            crawl_interval_hours=6,
        )
    )
    store.register_source(
        WebSource(
            url="https://example.com/docs",
            source_type="official_documentation",
            domain="domain_knowledge",
            crawl_interval_hours=168,
        )
    )
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    store.mark_source_crawled(
        "https://example.com/docs",
        crawled_at=now,
        content_hash="sha256:docs",
    )

    due = store.due_sources(now=now)

    assert [source.url for source in due] == ["https://example.com/jobs"]


def test_source_registry_reschedules_changed_page(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    source = WebSource(
        url="https://example.com/jobs/1",
        source_type="company_job_page",
        domain="job_opportunity",
        crawl_interval_hours=6,
    )
    store.register_source(source)
    first = datetime(2026, 10, 20, 0, tzinfo=UTC)
    store.mark_source_crawled(source.url, crawled_at=first, content_hash="sha256:v1")

    assert store.due_sources(now=datetime(2026, 10, 20, 5, tzinfo=UTC)) == ()
    assert store.due_sources(now=datetime(2026, 10, 20, 6, tzinfo=UTC))[0].url == source.url
