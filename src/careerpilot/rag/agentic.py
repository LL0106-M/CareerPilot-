from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from careerpilot.rag.models import KnowledgeOrigin, SearchHit
from careerpilot.rag.retrieval import RagRetriever
from careerpilot.rag.store import SqliteRagStore
from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource


class KnowledgeScope(StrEnum):
    JOBS = "jobs"
    PREPARATION = "preparation"
    PERSONAL = "personal"


_SCOPE_DOMAINS: dict[KnowledgeScope, tuple[str, ...]] = {
    KnowledgeScope.JOBS: ("job_opportunity",),
    KnowledgeScope.PREPARATION: (
        "preparation_material",
        "curated_document",
        "domain_knowledge",
        "ai_frontier",
    ),
    KnowledgeScope.PERSONAL: ("personal_material", "curated_document"),
}


class OnlineSearch(Protocol):
    async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse: ...


@dataclass(frozen=True, slots=True)
class AgenticRetrievalRequest:
    query: str
    scopes: tuple[KnowledgeScope, ...] = (
        KnowledgeScope.JOBS,
        KnowledgeScope.PREPARATION,
    )
    user_id: str | None = None
    sub_queries: tuple[str, ...] = ()
    minimum_sources: int = 1
    requires_freshness: bool = False
    limit: int = 5

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query is required")
        if not self.scopes:
            raise ValueError("at least one knowledge scope is required")
        if KnowledgeScope.PERSONAL in self.scopes and not self.user_id:
            raise ValueError("personal retrieval requires user_id")
        if self.minimum_sources < 1:
            raise ValueError("minimum_sources must be positive")
        if not 1 <= self.limit <= 20:
            raise ValueError("limit must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class AgenticRetrievalTrace:
    scopes: tuple[KnowledgeScope, ...]
    local_rounds: int
    online_rounds: int
    used_online_search: bool
    local_status: str
    stop_reason: str


@dataclass(frozen=True, slots=True)
class AgenticRetrievalResult:
    status: str
    hits: tuple[SearchHit, ...]
    online_sources: tuple[WebSearchSource, ...]
    online_answer: str
    needs_online_search: bool
    needs_ingestion: bool
    trace: AgenticRetrievalTrace


class AgenticRagOrchestrator:
    """Bounded retrieve-check-expand loop kept behind the product interface."""

    def __init__(
        self,
        store: SqliteRagStore,
        *,
        web_search: OnlineSearch | None = None,
        retriever: RagRetriever | None = None,
    ) -> None:
        self._retriever = retriever or RagRetriever(store)
        self._web_search = web_search

    async def retrieve(self, request: AgenticRetrievalRequest) -> AgenticRetrievalResult:
        hits: dict[str, SearchHit] = {}
        local_rounds = 0
        local_statuses: list[str] = []

        for scope in tuple(dict.fromkeys(request.scopes)):
            origins = _origins_for_scope(scope)
            for domain in _SCOPE_DOMAINS[scope]:
                result = self._retriever.retrieve(
                    request.query,
                    domain=domain,
                    sub_queries=request.sub_queries,
                    requires_freshness=request.requires_freshness,
                    validation_target=_validation_target(scope),
                    user_id=request.user_id,
                    origins=origins,
                    limit=request.limit,
                )
                local_rounds = max(local_rounds, result.rounds)
                local_statuses.append(result.status)
                for hit in result.hits:
                    key = hit.evidence_id or hit.chunk_id
                    existing = hits.get(key)
                    if existing is None or hit.score > existing.score:
                        hits[key] = hit

        ranked = sorted(
            hits.values(), key=lambda item: (-item.score, item.evidence_id or item.chunk_id)
        )
        ranked_hits = tuple(ranked[: request.limit])
        local_source_count = len({hit.source_uri for hit in ranked_hits})
        local_status = _combined_status(
            has_evidence=bool(ranked_hits),
            source_count=local_source_count,
            minimum_sources=request.minimum_sources,
            requires_freshness=request.requires_freshness,
        )
        if local_status == "available":
            return AgenticRetrievalResult(
                status="available",
                hits=ranked_hits,
                online_sources=(),
                online_answer="",
                needs_online_search=False,
                needs_ingestion=False,
                trace=AgenticRetrievalTrace(
                    scopes=request.scopes,
                    local_rounds=local_rounds,
                    online_rounds=0,
                    used_online_search=False,
                    local_status="available",
                    stop_reason="enough",
                ),
            )

        online_sources: dict[str, WebSearchSource] = {}
        online_answer = ""
        online_rounds = 0
        if self._web_search is not None and _allows_online_search(request.scopes):
            for strategy in (SearchStrategy.TURBO, SearchStrategy.MAX):
                response = await self._web_search.search(request.query, strategy)
                online_rounds += 1
                if response.answer:
                    online_answer = response.answer
                for source in response.sources:
                    online_sources.setdefault(source.url, source)
                combined_sources = local_source_count + len(online_sources)
                if combined_sources >= request.minimum_sources and online_sources:
                    break

        final_sources = tuple(online_sources.values())
        total_sources = local_source_count + len(final_sources)
        status = _combined_status(
            has_evidence=bool(ranked_hits or final_sources),
            source_count=total_sources,
            minimum_sources=request.minimum_sources,
            requires_freshness=False if final_sources else request.requires_freshness,
        )
        if final_sources:
            stop_reason = "online_evidence"
        elif self._web_search is None:
            stop_reason = "online_search_unavailable"
        else:
            stop_reason = "insufficient_evidence"
        return AgenticRetrievalResult(
            status=status,
            hits=ranked_hits,
            online_sources=final_sources,
            online_answer=online_answer,
            needs_online_search=status != "available",
            needs_ingestion=bool(final_sources),
            trace=AgenticRetrievalTrace(
                scopes=request.scopes,
                local_rounds=local_rounds,
                online_rounds=online_rounds,
                used_online_search=online_rounds > 0,
                local_status=local_status,
                stop_reason=stop_reason,
            ),
        )


def _origins_for_scope(scope: KnowledgeScope) -> frozenset[KnowledgeOrigin]:
    if scope is KnowledgeScope.JOBS:
        return frozenset({KnowledgeOrigin.SYSTEM_CURATED, KnowledgeOrigin.SYSTEM_WEB})
    if scope is KnowledgeScope.PERSONAL:
        return frozenset({KnowledgeOrigin.USER_PROVIDED})
    return frozenset(KnowledgeOrigin)


def _validation_target(scope: KnowledgeScope) -> str:
    if scope is KnowledgeScope.JOBS:
        return "current_job_opportunity"
    if scope is KnowledgeScope.PERSONAL:
        return "user_provided_evidence"
    return "preparation_material"


def _allows_online_search(scopes: tuple[KnowledgeScope, ...]) -> bool:
    return any(scope is not KnowledgeScope.PERSONAL for scope in scopes)


def _combined_status(
    *,
    has_evidence: bool,
    source_count: int,
    minimum_sources: int,
    requires_freshness: bool,
) -> str:
    if not has_evidence:
        return "insufficient"
    if source_count < minimum_sources or requires_freshness:
        return "partial"
    return "available"
