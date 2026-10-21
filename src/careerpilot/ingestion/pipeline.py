from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from careerpilot.ingestion.jobs import job_to_document, normalize_job_record
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.models import WebSource
from careerpilot.rag.store import SqliteRagStore


@dataclass(frozen=True, slots=True)
class PipelineResult:
    discovered: int
    indexed: int
    unchanged: int
    duplicates: int
    rejected: int
    errors: tuple[str, ...]


class JobIngestionPipeline:
    """Mage-style Source/Transform/Validate/Load flow without a scheduler dependency."""

    def __init__(self, store: SqliteRagStore, indexer: RagIndexer) -> None:
        self._store = store
        self._indexer = indexer

    def run(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        fetched_at: datetime,
    ) -> PipelineResult:
        indexed = 0
        unchanged = 0
        duplicates = 0
        rejected = 0
        errors: list[str] = []
        seen: set[str] = set()
        verified_at = fetched_at.date().isoformat()

        for position, raw in enumerate(records, start=1):
            try:
                job = normalize_job_record(raw, verified_at=verified_at)
            except ValueError as exc:
                rejected += 1
                errors.append(f"record {position}: {exc}")
                continue
            if job.identity in seen:
                duplicates += 1
                continue
            seen.add(job.identity)
            interval = 6 if job.source_level in {"S", "A"} else 24
            self._store.register_source(
                WebSource(
                    url=job.source_url,
                    source_type="job_source",
                    domain="job_opportunity",
                    crawl_interval_hours=interval,
                )
            )
            if self._store.source_content_hash(job.source_url) == job.content_hash:
                self._store.mark_source_crawled(
                    job.source_url,
                    crawled_at=fetched_at,
                    content_hash=job.content_hash,
                )
                unchanged += 1
                continue
            self._indexer.ingest_document(job_to_document(job, fetched_at=fetched_at))
            self._store.mark_source_crawled(
                job.source_url,
                crawled_at=fetched_at,
                content_hash=job.content_hash,
            )
            indexed += 1

        return PipelineResult(
            discovered=len(records),
            indexed=indexed,
            unchanged=unchanged,
            duplicates=duplicates,
            rejected=rejected,
            errors=tuple(errors),
        )
