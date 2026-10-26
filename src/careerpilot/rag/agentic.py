from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from careerpilot.rag.context import AgentContextPack, ContextAssembler
from careerpilot.rag.models import KnowledgeOrigin, SearchHit
from careerpilot.rag.query_analysis import GraphSearchMode, QueryAnalysis, RetrievalMode
from careerpilot.rag.retrieval import RagRetriever
from careerpilot.rag.routing import (
    ExternalQueryRoute,
    InternalQueryRoute,
    KnowledgeScope,
    RagQueryRouter,
)
from careerpilot.rag.store import SqliteRagStore
from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource


class OnlineSearch(Protocol):
    async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse: ...


@dataclass(frozen=True, slots=True)
class AgenticRetrievalRequest:
    query: str
    scopes: tuple[KnowledgeScope, ...] = ()
    user_id: str | None = None
    sub_queries: tuple[str, ...] = ()
    minimum_sources: int = 1
    requires_freshness: bool = False
    limit: int = 5

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query is required")
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
    external_route_reason: str
    internal_routes: tuple[str, ...]
    retrieval_mode: RetrievalMode
    graph_mode: GraphSearchMode
    query_intent: str


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    status: str
    relevant_evidence_count: int
    distinct_sources: int
    minimum_sources: int
    missing_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgenticRetrievalResult:
    status: str
    hits: tuple[SearchHit, ...]
    online_sources: tuple[WebSearchSource, ...]
    online_answer: str
    needs_online_search: bool
    needs_ingestion: bool
    trace: AgenticRetrievalTrace
    context_pack: AgentContextPack
    query_analysis: QueryAnalysis
    assessment: EvidenceAssessment


class AgenticRagOrchestrator:
    """Bounded retrieve-check-expand loop kept behind the product interface."""

    def __init__(
        self,
        store: SqliteRagStore,
        *,
        web_search: OnlineSearch | None = None,
        retriever: RagRetriever | None = None,
        router: RagQueryRouter | None = None,
        context_assembler: ContextAssembler | None = None,
    ) -> None:
        self._store = store
        self._retriever = retriever or RagRetriever(store)
        self._web_search = web_search
        self._router = router or RagQueryRouter()
        self._context_assembler = context_assembler or ContextAssembler()

    async def retrieve(self, request: AgenticRetrievalRequest) -> AgenticRetrievalResult:
        hits: dict[str, SearchHit] = {}
        local_rounds = 0
        external_route = self._router.route(
            request.query,
            requested_scopes=request.scopes,
            requires_freshness=request.requires_freshness,
            sub_queries=request.sub_queries,
        )
        if KnowledgeScope.PERSONAL in external_route.scopes and not request.user_id:
            raise ValueError("personal retrieval requires user_id")
        internal_routes = tuple(
            self._router.internal_route(
                request.query,
                scope,
                analysis=external_route.analysis,
            )
            for scope in external_route.scopes
        )

        if external_route.analysis.retrieval_mode is RetrievalMode.WEB_ONLY:
            online_answer, online_sources, online_rounds = await _search_online(
                self._web_search,
                external_route.analysis.normalized_query,
                minimum_sources=request.minimum_sources,
            )
            if online_sources or external_route.analysis.retrieval_mode is RetrievalMode.WEB_ONLY:
                assessment = _assess_evidence(
                    hits=(),
                    online_sources=online_sources,
                    minimum_sources=request.minimum_sources,
                    requires_freshness=False,
                )
                status = assessment.status
                return AgenticRetrievalResult(
                    status=status,
                    hits=(),
                    online_sources=online_sources,
                    online_answer=online_answer,
                    needs_online_search=status != "available",
                    needs_ingestion=bool(online_sources),
                    trace=_trace(
                        external_route=external_route,
                        internal_routes=internal_routes,
                        local_rounds=0,
                        online_rounds=online_rounds,
                        local_status="skipped",
                        stop_reason=("online_evidence" if online_sources else "online_unavailable"),
                    ),
                    context_pack=self._context_assembler.assemble(
                        status=status,
                        hits=(),
                        online_sources=online_sources,
                        online_answer=online_answer,
                    ),
                    query_analysis=external_route.analysis,
                    assessment=assessment,
                )

        for internal_route in internal_routes:
            origins = _origins_for_scope(internal_route.scope)
            if internal_route.scope is KnowledgeScope.JOBS:
                for hit in self._store.search_job_records(
                    request.query,
                    limit=request.limit,
                ):
                    hits[hit.evidence_id or hit.chunk_id] = hit
            for domain in internal_route.domains:
                result = self._retriever.retrieve(
                    request.query,
                    domain=domain,
                    sub_queries=request.sub_queries,
                    requires_freshness=external_route.requires_freshness,
                    validation_target=internal_route.validation_target,
                    user_id=request.user_id,
                    origins=origins,
                    use_graph=internal_route.use_graph,
                    graph_mode=internal_route.graph_mode,
                    limit=request.limit,
                )
                local_rounds = max(local_rounds, result.rounds)
                for hit in result.hits:
                    key = hit.evidence_id or hit.chunk_id
                    existing = hits.get(key)
                    if existing is None or hit.score > existing.score:
                        hits[key] = hit

        ranked = sorted(
            hits.values(), key=lambda item: (-item.score, item.evidence_id or item.chunk_id)
        )
        ranked_hits = tuple(ranked[: request.limit])
        local_assessment = _assess_evidence(
            hits=ranked_hits,
            online_sources=(),
            minimum_sources=request.minimum_sources,
            requires_freshness=external_route.requires_freshness,
        )
        local_source_count = local_assessment.distinct_sources
        local_status = local_assessment.status
        if local_status == "available":
            return AgenticRetrievalResult(
                status="available",
                hits=ranked_hits,
                online_sources=(),
                online_answer="",
                needs_online_search=False,
                needs_ingestion=False,
                trace=_trace(
                    external_route=external_route,
                    internal_routes=internal_routes,
                    local_rounds=local_rounds,
                    online_rounds=0,
                    local_status="available",
                    stop_reason="enough",
                ),
                context_pack=self._context_assembler.assemble(
                    status="available",
                    hits=ranked_hits,
                ),
                query_analysis=external_route.analysis,
                assessment=local_assessment,
            )

        online_sources: dict[str, WebSearchSource] = {}
        online_answer = ""
        online_rounds = 0
        allow_online_search = any(route.allow_online_search for route in internal_routes)
        if allow_online_search:
            answer, sources, rounds = await _search_online(
                self._web_search,
                external_route.analysis.normalized_query,
                minimum_sources=max(1, request.minimum_sources - local_source_count),
            )
            online_answer = answer
            online_rounds = rounds
            online_sources.update({source.url: source for source in sources})

        final_sources = tuple(online_sources.values())
        assessment = _assess_evidence(
            hits=ranked_hits,
            online_sources=final_sources,
            minimum_sources=request.minimum_sources,
            requires_freshness=False if final_sources else external_route.requires_freshness,
        )
        status = assessment.status
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
            trace=_trace(
                external_route=external_route,
                internal_routes=internal_routes,
                local_rounds=local_rounds,
                online_rounds=online_rounds,
                local_status=local_status,
                stop_reason=stop_reason,
            ),
            context_pack=self._context_assembler.assemble(
                status=status,
                hits=ranked_hits,
                online_sources=final_sources,
                online_answer=online_answer,
            ),
            query_analysis=external_route.analysis,
            assessment=assessment,
        )


async def _search_online(
    provider: OnlineSearch | None,
    query: str,
    *,
    minimum_sources: int,
) -> tuple[str, tuple[WebSearchSource, ...], int]:
    if provider is None:
        return "", (), 0
    answer = ""
    sources: dict[str, WebSearchSource] = {}
    rounds = 0
    for strategy in (SearchStrategy.TURBO, SearchStrategy.MAX):
        response = await provider.search(query, strategy)
        rounds += 1
        if response.answer:
            answer = response.answer
        for source in response.sources:
            sources.setdefault(source.url, source)
        if len(sources) >= minimum_sources:
            break
    return answer, tuple(sources.values()), rounds


def _trace(
    *,
    external_route: ExternalQueryRoute,
    internal_routes: tuple[InternalQueryRoute, ...],
    local_rounds: int,
    online_rounds: int,
    local_status: str,
    stop_reason: str,
) -> AgenticRetrievalTrace:
    analysis = external_route.analysis
    return AgenticRetrievalTrace(
        scopes=external_route.scopes,
        local_rounds=local_rounds,
        online_rounds=online_rounds,
        used_online_search=online_rounds > 0,
        local_status=local_status,
        stop_reason=stop_reason,
        external_route_reason=external_route.reason,
        internal_routes=tuple(_route_label(route) for route in internal_routes),
        retrieval_mode=analysis.retrieval_mode,
        graph_mode=analysis.graph_mode,
        query_intent=analysis.intent.value,
    )


def _origins_for_scope(scope: KnowledgeScope) -> frozenset[KnowledgeOrigin]:
    if scope is KnowledgeScope.JOBS:
        return frozenset({KnowledgeOrigin.SYSTEM_CURATED, KnowledgeOrigin.SYSTEM_WEB})
    if scope is KnowledgeScope.PERSONAL:
        return frozenset({KnowledgeOrigin.USER_PROVIDED})
    return frozenset({KnowledgeOrigin.SYSTEM_CURATED, KnowledgeOrigin.SYSTEM_WEB})


def _route_label(route: InternalQueryRoute) -> str:
    return f"{route.scope.value}:{','.join(channel.value for channel in route.channels)}"


def _assess_evidence(
    *,
    hits: tuple[SearchHit, ...],
    online_sources: tuple[WebSearchSource, ...],
    minimum_sources: int,
    requires_freshness: bool,
) -> EvidenceAssessment:
    relevant_hits = tuple(
        hit for hit in hits if hit.source_uri and hit.score >= 0.20 and hit.content.strip()
    )
    citable_online = tuple(
        source for source in online_sources if source.url and (source.snippet or source.title)
    )
    source_uris = {hit.source_uri for hit in relevant_hits}
    source_uris.update(source.url for source in citable_online)
    reasons: list[str] = []
    relevant_count = len(relevant_hits) + len(citable_online)
    if relevant_count == 0:
        reasons.append("no_relevant_evidence")
    if len(source_uris) < minimum_sources:
        reasons.append("not_enough_distinct_sources")
    if requires_freshness and not citable_online and not _has_fresh_local_evidence(relevant_hits):
        reasons.append("freshness_not_verified")
    if not relevant_count:
        status = "insufficient"
    elif reasons:
        status = "partial"
    else:
        status = "available"
    return EvidenceAssessment(
        status=status,
        relevant_evidence_count=relevant_count,
        distinct_sources=len(source_uris),
        minimum_sources=minimum_sources,
        missing_reasons=tuple(reasons),
    )


def _has_fresh_local_evidence(hits: tuple[SearchHit, ...]) -> bool:
    now = datetime.now(UTC)
    for hit in hits:
        raw = next(
            (
                hit.metadata.get(key)
                for key in ("verified_at", "fetched_at", "updated_at")
                if hit.metadata.get(key)
            ),
            None,
        )
        if not isinstance(raw, str):
            continue
        try:
            observed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        maximum_age = timedelta(hours=72 if hit.domain == "job_opportunity" else 24 * 30)
        if now - observed.astimezone(UTC) <= maximum_age:
            return True
    return False
