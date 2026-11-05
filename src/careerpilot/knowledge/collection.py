import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

from careerpilot.product_store import ProductStore
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.models import KnowledgeOrigin, SourceDocument
from careerpilot.rag.store import SqliteRagStore
from careerpilot.search.models import SearchStrategy, WebSearchResponse


class OnlineSearch(Protocol):
    async def search(
        self, query: str, strategy: SearchStrategy = SearchStrategy.TURBO
    ) -> WebSearchResponse: ...


@dataclass(frozen=True, slots=True)
class CollectionRunResult:
    processed: int
    saved: int


_PURPOSE_CONFIG = {
    "job_opportunity": ("最新招聘 官方", "job_source"),
    "interview_archive": ("往年面试题 面经", "interview_experience"),
    "learning_resource": ("学习资料 官方指南", "learning_resource"),
}


class KnowledgeCollectionProcessor:
    def __init__(
        self,
        product: ProductStore,
        rag: SqliteRagStore,
        search: OnlineSearch | None,
    ) -> None:
        self._product = product
        self._rag = rag
        self._search = search

    async def process_for_owner(
        self, owner_id: str, *, purpose: str, limit: int = 3
    ) -> CollectionRunResult:
        jobs = self._product.claim_collection_jobs(
            owner_id, purpose=purpose, limit=limit
        )
        saved_total = 0
        for job in jobs:
            job_id = str(job["id"])
            if self._search is None:
                self._product.finish_collection_job(
                    owner_id,
                    job_id,
                    status="failed",
                    last_error="search_not_configured",
                )
                continue
            try:
                saved = await self._collect(job)
            except Exception as exc:
                self._product.finish_collection_job(
                    owner_id,
                    job_id,
                    status="failed",
                    last_error=type(exc).__name__,
                )
                continue
            saved_total += saved
            self._product.finish_collection_job(
                owner_id,
                job_id,
                status="completed" if saved else "partial",
                result_count=saved,
                last_error=None if saved else "no_sources_found",
            )
        return CollectionRunResult(processed=len(jobs), saved=saved_total)

    async def _collect(self, job: dict[str, object]) -> int:
        purpose = str(job["purpose"])
        suffix, domain = _PURPOSE_CONFIG[purpose]
        response = await self._search.search(
            f"{str(job['query']).strip()} {suffix}", SearchStrategy.TURBO
        )
        fetched_at = datetime.now(UTC).isoformat()
        saved = 0
        for source in response.sources:
            parsed = urlsplit(source.url.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            record_id = f"collected-{hashlib.sha256(source.url.encode()).hexdigest()[:20]}"
            metadata: dict[str, object] = {
                "publisher": source.site_name or "来源网页",
                "collection_job_id": job["id"],
                "direction_id": job["direction_id"],
            }
            if purpose == "interview_archive":
                metadata["trust"] = "unverified"
            elif purpose == "learning_resource":
                metadata.update({"category": "其他", "format": "网页"})
            RagIndexer(self._rag).ingest_document(
                SourceDocument(
                    id=record_id,
                    title=source.title.strip() or source.url,
                    source_uri=source.url,
                    source_type="web_search",
                    domain=domain,
                    text=(source.snippet or source.title or source.url).strip(),
                    metadata=metadata,
                    fetched_at=fetched_at,
                    knowledge_origin=KnowledgeOrigin.SYSTEM_WEB,
                )
            )
            saved += 1
        return saved
