from careerpilot.rag.routing import (
    KnowledgeScope,
    RagQueryRouter,
    RetrievalChannel,
)


def test_external_router_infers_jobs_and_freshness() -> None:
    router = RagQueryRouter()

    route = router.route("最近有哪些产品经理岗位还在招聘")

    assert route.scopes == (KnowledgeScope.JOBS,)
    assert route.requires_freshness is True
    assert route.reason == "rule_inference"


def test_explicit_external_scope_overrides_rule_inference() -> None:
    router = RagQueryRouter()

    route = router.route(
        "分析我的项目经历",
        requested_scopes=(KnowledgeScope.PREPARATION,),
    )

    assert route.scopes == (KnowledgeScope.PREPARATION,)
    assert route.reason == "explicit_upstream_scope"


def test_internal_router_enables_graph_only_for_relational_preparation_query() -> None:
    router = RagQueryRouter()

    direct = router.internal_route("什么是需求分析", KnowledgeScope.PREPARATION)
    relational = router.internal_route(
        "用户研究能力如何影响需求分析能力",
        KnowledgeScope.PREPARATION,
    )

    assert RetrievalChannel.GRAPH not in direct.channels
    assert direct.use_graph is False
    assert RetrievalChannel.GRAPH in relational.channels
    assert relational.use_graph is True


def test_personal_route_never_uses_public_graph_or_online_search() -> None:
    route = RagQueryRouter().internal_route("分析我的简历", KnowledgeScope.PERSONAL)

    assert route.channels == (RetrievalChannel.SPARSE, RetrievalChannel.DENSE)
    assert route.use_graph is False
    assert route.allow_online_search is False
