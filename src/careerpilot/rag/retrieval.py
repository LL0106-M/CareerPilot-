import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from careerpilot.rag.models import EvidenceKind, SearchHit
from careerpilot.rag.store import SqliteRagStore


@dataclass(frozen=True, slots=True)
class QueryPlan:
    domain: str | None
    validation_target: str
    queries: tuple[str, ...]
    minimum_sources: int
    requires_freshness: bool
    max_rounds: int = 2


@dataclass(frozen=True, slots=True)
class RetrievalClue:
    evidence_id: str
    claim: str
    role: str
    source_uri: str


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    status: str
    plan: QueryPlan
    hits: tuple[SearchHit, ...]
    distinct_sources: int
    needs_online_search: bool
    clues: tuple[RetrievalClue, ...] = ()
    rounds: int = 1
    stop_reason: str = "enough"


class Planner(Protocol):
    def plan(self, query: str, **kwargs: object) -> QueryPlan: ...


QueryRewriter = Callable[[QueryPlan, int], tuple[str, ...]]


class QueryPlanner:
    """Build an explicit plan without guessing domains from keyword marker lists."""

    def __init__(self, *, default_minimum_sources: int = 1, max_rounds: int = 2) -> None:
        self._default_minimum_sources = max(1, default_minimum_sources)
        self._max_rounds = max(1, min(max_rounds, 3))

    def plan(
        self,
        query: str,
        *,
        domain: str | None = None,
        sub_queries: tuple[str, ...] = (),
        requires_freshness: bool = False,
        validation_target: str = "direct_fact",
    ) -> QueryPlan:
        normalized = _normalize(query)
        queries = tuple(
            dict.fromkeys(item for item in (normalized, *map(_normalize, sub_queries)) if item)
        )
        return QueryPlan(
            domain=domain,
            validation_target=validation_target,
            queries=queries,
            minimum_sources=self._default_minimum_sources,
            requires_freshness=requires_freshness,
            max_rounds=self._max_rounds,
        )


class RagRetriever:
    """Hybrid evidence retrieval with query-to-triple graph expansion and bounded stopping."""

    def __init__(
        self,
        store: SqliteRagStore,
        planner: Planner | None = None,
        *,
        query_rewriter: QueryRewriter | None = None,
    ) -> None:
        self._store = store
        self._planner = planner or QueryPlanner()
        self._query_rewriter = query_rewriter

    def retrieve(
        self,
        query: str,
        *,
        domain: str | None = None,
        sub_queries: tuple[str, ...] = (),
        requires_freshness: bool = False,
        validation_target: str = "direct_fact",
        limit: int = 5,
    ) -> RetrievalResult:
        plan = self._planner.plan(
            query,
            domain=domain,
            sub_queries=sub_queries,
            requires_freshness=requires_freshness,
            validation_target=validation_target,
        )
        if not plan.queries:
            return RetrievalResult(
                status="insufficient",
                plan=plan,
                hits=(),
                distinct_sources=0,
                needs_online_search=True,
                stop_reason="needs_online_search",
            )

        candidate_limit = max(limit * 3, 15)
        accumulated: dict[str, SearchHit] = {}
        clues: dict[str, RetrievalClue] = {}
        round_queries = plan.queries
        final_hits: tuple[SearchHit, ...] = ()
        status = "insufficient"
        stop_reason = "needs_online_search"
        rounds = 0

        for round_number in range(1, plan.max_rounds + 1):
            rounds = round_number
            ranked_lists = self._retrieve_round(
                round_queries,
                domain=plan.domain,
                candidate_limit=candidate_limit,
            )
            fused = _rrf_fuse(ranked_lists, candidate_limit)
            new_ids = {
                hit.evidence_id
                for hit in fused
                if hit.evidence_id and hit.evidence_id not in accumulated
            }
            for hit in fused:
                if hit.evidence_id:
                    accumulated[hit.evidence_id] = hit
                    clues.setdefault(hit.evidence_id, _to_clue(hit))

            final_hits = _quality_rerank(tuple(accumulated.values()), limit)
            distinct_sources = len({hit.source_uri for hit in final_hits})
            status = _status(final_hits, distinct_sources, plan)
            if status == "available":
                stop_reason = "enough"
                break
            if round_number > 1 and not new_ids:
                stop_reason = "no_new_evidence"
                break
            if self._query_rewriter is None:
                stop_reason = "needs_online_search"
                break
            if round_number == plan.max_rounds:
                stop_reason = "max_depth"
                break
            round_queries = tuple(
                dict.fromkeys(
                    item
                    for item in map(_normalize, self._query_rewriter(plan, round_number))
                    if item
                )
            )
            if not round_queries:
                stop_reason = "needs_online_search"
                break

        distinct_sources = len({hit.source_uri for hit in final_hits})
        return RetrievalResult(
            status=status,
            plan=plan,
            hits=final_hits,
            distinct_sources=distinct_sources,
            needs_online_search=status != "available",
            clues=tuple(clues.values()),
            rounds=rounds,
            stop_reason=stop_reason,
        )

    def _retrieve_round(
        self,
        queries: tuple[str, ...],
        *,
        domain: str | None,
        candidate_limit: int,
    ) -> list[tuple[str, tuple[SearchHit, ...]]]:
        ranked_lists: list[tuple[str, tuple[SearchHit, ...]]] = []
        triple_kinds = frozenset({EvidenceKind.KG_TRIPLE})
        triple_seeds: list[SearchHit] = []
        for index, current_query in enumerate(queries):
            sparse = self._store.search_sparse(
                current_query,
                domain=domain,
                limit=candidate_limit,
            )
            dense = self._store.search_dense(
                current_query,
                domain=domain,
                limit=candidate_limit,
            )
            triple_sparse = self._store.search_sparse(
                current_query,
                domain=domain,
                kinds=triple_kinds,
                limit=min(candidate_limit, 20),
            )
            triple_dense = self._store.search_dense(
                current_query,
                domain=domain,
                kinds=triple_kinds,
                limit=min(candidate_limit, 20),
            )
            ranked_lists.extend(
                [
                    (f"sparse:{index}", sparse),
                    (f"dense:{index}", dense),
                    (f"triple_sparse:{index}", triple_sparse),
                    (f"triple_dense:{index}", triple_dense),
                ]
            )
            # Expand only the strongest linked statement per query in the MVP.
            # This keeps graph work bounded and lets neighboring facts add evidence.
            triple_seeds.extend(triple_dense[:1] or triple_sparse[:1])
        graph = self._store.neighbors(
            (hit.evidence_id for hit in triple_seeds),
            limit=min(candidate_limit, 20),
        )
        if graph:
            ranked_lists.append(("graph:local", graph))
        return ranked_lists


def _rrf_fuse(
    ranked_lists: list[tuple[str, tuple[SearchHit, ...]]],
    limit: int,
    *,
    k: int = 60,
) -> tuple[SearchHit, ...]:
    scores: dict[str, float] = {}
    hits: dict[str, SearchHit] = {}
    channels: dict[str, set[str]] = {}
    best_rank: dict[str, int] = {}
    for source_name, ranked in ranked_lists:
        channel = source_name.split(":", 1)[0].replace("triple_", "")
        for rank, hit in enumerate(ranked, start=1):
            evidence_id = hit.evidence_id or hit.chunk_id
            scores[evidence_id] = scores.get(evidence_id, 0.0) + 1.0 / (k + rank)
            channels.setdefault(evidence_id, set()).update((*hit.channels, channel))
            if evidence_id not in hits or rank < best_rank[evidence_id]:
                hits[evidence_id] = hit
                best_rank[evidence_id] = rank
    ordered = sorted(scores, key=lambda evidence_id: (-scores[evidence_id], evidence_id))[:limit]
    return tuple(
        replace(
            hits[evidence_id],
            score=scores[evidence_id],
            channels=tuple(sorted(channels[evidence_id])),
        )
        for evidence_id in ordered
    )


def _quality_rerank(hits: tuple[SearchHit, ...], limit: int) -> tuple[SearchHit, ...]:
    if not hits:
        return ()
    max_rrf = max(hit.score for hit in hits) or 1.0
    rescored: list[SearchHit] = []
    for hit in hits:
        tier = _source_tier(hit)
        authority = {1: 1.0, 2: 0.8, 3: 0.55, 4: 0.3}.get(tier, 0.5)
        role = _evidence_role(hit)
        directness = 1.0 if role == "direct" else 0.7
        channel_support = min(len(hit.channels) / 3.0, 1.0)
        final_score = (
            0.7 * (hit.score / max_rrf)
            + 0.15 * authority
            + 0.1 * directness
            + 0.05 * channel_support
        )
        metadata = {**hit.metadata, "evidence_role": role, "source_tier": tier}
        rescored.append(replace(hit, score=final_score, metadata=metadata))
    rescored.sort(key=lambda hit: (-hit.score, hit.evidence_id or hit.chunk_id))
    return tuple(rescored[: max(1, min(limit, 20))])


def _source_tier(hit: SearchHit) -> int:
    raw = hit.metadata.get("source_tier")
    if isinstance(raw, int) and 1 <= raw <= 4:
        return raw
    return 1 if "official" in hit.source_type else 3


def _evidence_role(hit: SearchHit) -> str:
    if "graph" in hit.channels:
        return "bridge"
    if hit.evidence_kind in {EvidenceKind.PASSAGE, EvidenceKind.TABLE_ROW}:
        return "direct"
    return "background"


def _to_clue(hit: SearchHit) -> RetrievalClue:
    return RetrievalClue(
        evidence_id=hit.evidence_id or hit.chunk_id,
        claim=hit.content,
        role=_evidence_role(hit),
        source_uri=hit.source_uri,
    )


def _status(
    hits: tuple[SearchHit, ...],
    distinct_sources: int,
    plan: QueryPlan,
) -> str:
    if not hits:
        return "insufficient"
    if distinct_sources < plan.minimum_sources or plan.requires_freshness:
        return "partial"
    return "available"


def _normalize(query: str) -> str:
    return re.sub(r"[？?！!。；;，,]+$", "", " ".join(query.split())).strip()
