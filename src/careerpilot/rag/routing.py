import re
from dataclasses import dataclass
from enum import StrEnum

from careerpilot.rag.query_analysis import (
    CostAwareQueryAnalyzer,
    GraphSearchMode,
    QueryAnalysis,
    RetrievalMode,
)


class KnowledgeScope(StrEnum):
    JOBS = "jobs"
    PREPARATION = "preparation"
    PERSONAL = "personal"


class RetrievalChannel(StrEnum):
    STRUCTURED = "structured"
    SPARSE = "sparse"
    DENSE = "dense"
    GRAPH = "graph"
    ONLINE = "online"


SCOPE_DOMAINS: dict[KnowledgeScope, tuple[str, ...]] = {
    KnowledgeScope.JOBS: ("job_opportunity",),
    KnowledgeScope.PREPARATION: (
        "preparation_material",
        "curated_document",
        "domain_knowledge",
        "ai_frontier",
    ),
    KnowledgeScope.PERSONAL: ("personal_material", "curated_document"),
}


@dataclass(frozen=True, slots=True)
class ExternalQueryRoute:
    scopes: tuple[KnowledgeScope, ...]
    requires_freshness: bool
    reason: str
    analysis: QueryAnalysis


@dataclass(frozen=True, slots=True)
class InternalQueryRoute:
    scope: KnowledgeScope
    domains: tuple[str, ...]
    channels: tuple[RetrievalChannel, ...]
    use_graph: bool
    graph_mode: GraphSearchMode
    retrieval_mode: RetrievalMode
    allow_online_search: bool
    validation_target: str


class RagQueryRouter:
    """Rule-first RAG routing; explicit upstream scopes always take precedence."""

    _job_pattern = re.compile(r"岗位|职位|招聘|校招|社招|投递|内推|JD|截止|在招", re.I)
    _prep_pattern = re.compile(r"面试|面经|备考|准备|学习资料|题目|怎么回答|知识点", re.I)
    _personal_pattern = re.compile(r"我的|简历|我上传|个人资料|项目经历|工作经历", re.I)

    def __init__(self, analyzer: CostAwareQueryAnalyzer | None = None) -> None:
        self._analyzer = analyzer or CostAwareQueryAnalyzer()

    def route(
        self,
        query: str,
        *,
        requested_scopes: tuple[KnowledgeScope, ...] = (),
        requires_freshness: bool = False,
        sub_queries: tuple[str, ...] = (),
    ) -> ExternalQueryRoute:
        if requested_scopes:
            scopes = tuple(dict.fromkeys(requested_scopes))
            reason = "explicit_upstream_scope"
        else:
            inferred: list[KnowledgeScope] = []
            if self._personal_pattern.search(query):
                inferred.append(KnowledgeScope.PERSONAL)
            if self._job_pattern.search(query):
                inferred.append(KnowledgeScope.JOBS)
            if self._prep_pattern.search(query):
                inferred.append(KnowledgeScope.PREPARATION)
            scopes = tuple(dict.fromkeys(inferred)) or (KnowledgeScope.PREPARATION,)
            reason = "rule_inference" if inferred else "default_preparation"
        analysis = self._analyzer.analyze(
            query,
            has_jobs=KnowledgeScope.JOBS in scopes,
            has_preparation=KnowledgeScope.PREPARATION in scopes,
            has_personal=KnowledgeScope.PERSONAL in scopes,
            requires_freshness=requires_freshness,
            sub_queries=sub_queries,
        )
        return ExternalQueryRoute(scopes, analysis.requires_freshness, reason, analysis)

    def internal_route(
        self,
        query: str,
        scope: KnowledgeScope,
        *,
        analysis: QueryAnalysis | None = None,
    ) -> InternalQueryRoute:
        resolved = analysis or self._analyzer.analyze(
            query,
            has_jobs=scope is KnowledgeScope.JOBS,
            has_preparation=scope is KnowledgeScope.PREPARATION,
            has_personal=scope is KnowledgeScope.PERSONAL,
        )
        if scope is KnowledgeScope.JOBS:
            channels = (
                (RetrievalChannel.ONLINE,)
                if resolved.retrieval_mode is RetrievalMode.WEB_ONLY
                else (
                    RetrievalChannel.STRUCTURED,
                    RetrievalChannel.SPARSE,
                    RetrievalChannel.DENSE,
                    RetrievalChannel.ONLINE,
                )
            )
            return InternalQueryRoute(
                scope=scope,
                domains=SCOPE_DOMAINS[scope],
                channels=channels,
                use_graph=False,
                graph_mode=GraphSearchMode.NONE,
                retrieval_mode=resolved.retrieval_mode,
                allow_online_search=True,
                validation_target="current_job_opportunity",
            )
        if scope is KnowledgeScope.PERSONAL:
            return InternalQueryRoute(
                scope=scope,
                domains=SCOPE_DOMAINS[scope],
                channels=(RetrievalChannel.SPARSE, RetrievalChannel.DENSE),
                use_graph=False,
                graph_mode=GraphSearchMode.NONE,
                retrieval_mode=RetrievalMode.LOCAL_ONLY,
                allow_online_search=False,
                validation_target="user_provided_evidence",
            )
        use_graph = resolved.graph_mode is not GraphSearchMode.NONE
        channels = [RetrievalChannel.SPARSE, RetrievalChannel.DENSE]
        if use_graph:
            channels.append(RetrievalChannel.GRAPH)
        channels.append(RetrievalChannel.ONLINE)
        return InternalQueryRoute(
            scope=scope,
            domains=SCOPE_DOMAINS[scope],
            channels=tuple(channels),
            use_graph=use_graph,
            graph_mode=resolved.graph_mode,
            retrieval_mode=resolved.retrieval_mode,
            allow_online_search=True,
            validation_target="preparation_material",
        )
