import re
from dataclasses import dataclass, field
from enum import StrEnum


class RetrievalMode(StrEnum):
    WEB_ONLY = "web_only"
    LOCAL_ONLY = "local_only"
    LOCAL_FIRST = "local_first"
    WEB_FIRST = "web_first"
    HYBRID = "hybrid"


class GraphSearchMode(StrEnum):
    NONE = "none"
    LOCAL = "local"
    GLOBAL = "global"
    HIERARCHICAL = "hierarchical"


class QueryIntent(StrEnum):
    JOB_DISCOVERY = "job_discovery"
    JOB_MATCH = "job_match"
    PERSONAL_ANALYSIS = "personal_analysis"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    RELATIONAL_REASONING = "relational_reasoning"
    GLOBAL_SYNTHESIS = "global_synthesis"


@dataclass(frozen=True, slots=True)
class QueryAnalysis:
    original_query: str
    normalized_query: str
    intent: QueryIntent
    retrieval_mode: RetrievalMode
    graph_mode: GraphSearchMode
    requires_freshness: bool
    entities: dict[str, str] = field(default_factory=dict)
    sub_queries: tuple[str, ...] = ()
    reason: str = "rule_analysis"


class CostAwareQueryAnalyzer:
    """Cheap deterministic query understanding before any embedding or LLM call."""

    _job = re.compile(r"岗位|职位|招聘|校招|社招|投递|内推|JD|截止|在招", re.I)
    _personal = re.compile(r"我的|简历|我上传|个人资料|项目经历|工作经历", re.I)
    _fresh = re.compile(r"最新|现在|目前|今天|近期|今年|截止|在招|开放", re.I)
    _explicit_web = re.compile(r"联网|网上|全网|搜索|搜一下|查一下", re.I)
    _relational = re.compile(
        r"为什么|如何.*影响|关联|关系|联系|路径|迁移|对比|区别|共同|多跳|前置",
        re.I,
    )
    _global = re.compile(r"整体|完整|体系|全貌|共性|趋势|所有|普遍|总结|归纳", re.I)
    _hierarchical = re.compile(r"分别|每类|分类|逐类|举例|证据|如何体现", re.I)
    _job_match = re.compile(r"适合|匹配|差距|胜任|符合|契合", re.I)
    _organization_types = ("国企", "央企", "民企", "外企", "事业单位", "政府")
    _role_families = {
        "产品": "product",
        "开发": "engineering",
        "研发": "engineering",
        "算法": "algorithm",
        "运营": "operations",
        "设计": "design",
        "测试": "quality_assurance",
        "数据": "data",
    }
    _recruiting_types = {
        "实习": "internship",
        "校招": "campus",
        "应届": "campus",
        "社招": "experienced",
    }
    _locations = (
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州",
        "南京",
        "成都",
        "武汉",
        "西安",
        "苏州",
    )

    def analyze(
        self,
        query: str,
        *,
        has_jobs: bool,
        has_preparation: bool,
        has_personal: bool,
        requires_freshness: bool = False,
        sub_queries: tuple[str, ...] = (),
    ) -> QueryAnalysis:
        normalized = _normalize(query)
        fresh = requires_freshness or bool(self._fresh.search(normalized))
        explicit_web = bool(self._explicit_web.search(normalized))
        relational = bool(self._relational.search(normalized))
        broad = bool(self._global.search(normalized))
        match = has_jobs and has_personal and bool(self._job_match.search(normalized))

        if match:
            intent = QueryIntent.JOB_MATCH
            retrieval_mode = RetrievalMode.HYBRID
        elif has_personal and not (has_jobs or has_preparation):
            intent = QueryIntent.PERSONAL_ANALYSIS
            retrieval_mode = RetrievalMode.LOCAL_ONLY
        elif has_jobs and (fresh or explicit_web) and not has_personal:
            intent = QueryIntent.JOB_DISCOVERY
            retrieval_mode = RetrievalMode.WEB_ONLY
            fresh = True
        elif explicit_web or fresh:
            intent = QueryIntent.KNOWLEDGE_LOOKUP
            retrieval_mode = RetrievalMode.WEB_FIRST
        elif broad and has_preparation:
            intent = QueryIntent.GLOBAL_SYNTHESIS
            retrieval_mode = RetrievalMode.LOCAL_FIRST
        elif relational and has_preparation:
            intent = QueryIntent.RELATIONAL_REASONING
            retrieval_mode = RetrievalMode.LOCAL_FIRST
        else:
            intent = QueryIntent.KNOWLEDGE_LOOKUP
            retrieval_mode = RetrievalMode.LOCAL_FIRST

        graph_mode = GraphSearchMode.NONE
        if has_preparation:
            if broad and self._hierarchical.search(normalized):
                graph_mode = GraphSearchMode.HIERARCHICAL
            elif broad:
                graph_mode = GraphSearchMode.GLOBAL
            elif relational:
                graph_mode = GraphSearchMode.LOCAL

        entities: dict[str, str] = {}
        for organization_type in self._organization_types:
            if organization_type in normalized:
                entities["organization_type"] = organization_type
                break
        for location in self._locations:
            if location in normalized:
                entities["location"] = location
                break
        for marker, role_family in self._role_families.items():
            if marker in normalized:
                entities["role_family"] = role_family
                break
        for marker, recruiting_type in self._recruiting_types.items():
            if marker in normalized:
                entities["recruiting_type"] = recruiting_type
                break

        queries = tuple(dict.fromkeys(item for item in map(_normalize, sub_queries) if item))
        return QueryAnalysis(
            original_query=query,
            normalized_query=normalized,
            intent=intent,
            retrieval_mode=retrieval_mode,
            graph_mode=graph_mode,
            requires_freshness=fresh,
            entities=entities,
            sub_queries=queries,
        )


def _normalize(query: str) -> str:
    return re.sub(r"[？?！!。；;，,]+$", "", " ".join(query.split())).strip()
