from careerpilot.rag.query_analysis import (
    CostAwareQueryAnalyzer,
    GraphSearchMode,
    QueryIntent,
    RetrievalMode,
)


def test_fresh_job_discovery_is_web_only_and_extracts_slots() -> None:
    result = CostAwareQueryAnalyzer().analyze(
        "帮我搜索上海国企最新开放的产品经理岗位",
        has_jobs=True,
        has_preparation=False,
        has_personal=False,
    )

    assert result.intent is QueryIntent.JOB_DISCOVERY
    assert result.retrieval_mode is RetrievalMode.WEB_ONLY
    assert result.graph_mode is GraphSearchMode.NONE
    assert result.requires_freshness is True
    assert result.entities == {
        "organization_type": "国企",
        "location": "上海",
        "role_family": "product",
    }


def test_relational_preparation_query_uses_local_graph() -> None:
    result = CostAwareQueryAnalyzer().analyze(
        "用户研究能力如何影响需求分析能力",
        has_jobs=False,
        has_preparation=True,
        has_personal=False,
    )

    assert result.intent is QueryIntent.RELATIONAL_REASONING
    assert result.retrieval_mode is RetrievalMode.LOCAL_FIRST
    assert result.graph_mode is GraphSearchMode.LOCAL


def test_broad_classified_query_uses_hierarchical_graph() -> None:
    result = CostAwareQueryAnalyzer().analyze(
        "总结完整的产品经理能力体系，并分别给出每类证据",
        has_jobs=False,
        has_preparation=True,
        has_personal=False,
    )

    assert result.intent is QueryIntent.GLOBAL_SYNTHESIS
    assert result.graph_mode is GraphSearchMode.HIERARCHICAL


def test_private_query_never_uses_web_or_public_graph() -> None:
    result = CostAwareQueryAnalyzer().analyze(
        "分析我的简历和项目经历",
        has_jobs=False,
        has_preparation=False,
        has_personal=True,
    )

    assert result.intent is QueryIntent.PERSONAL_ANALYSIS
    assert result.retrieval_mode is RetrievalMode.LOCAL_ONLY
    assert result.graph_mode is GraphSearchMode.NONE
