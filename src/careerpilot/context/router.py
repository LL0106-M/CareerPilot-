from careerpilot.context.contracts import (
    IntentFrame,
    RetrievalPlan,
    RetrievalRoute,
    RetrievalSource,
    TaskIntent,
)
from careerpilot.support.policy import SupportMode


class IntentAwareRetrievalRouter:
    """Map semantic intent to governed context sources and tool capabilities."""

    _personal_reference_markers = (
        "结合我的",
        "根据我的",
        "按照我的",
        "我的情况",
        "我的偏好",
        "上次",
        "之前",
        "还记得",
        "一直",
        "总是",
        "记住",
    )
    _private_document_markers = (
        "简历",
        "履历",
        "作品集",
        "我的资料",
        "JD",
        "jd",
        "岗位描述",
        "面试笔记",
    )
    _freshness_markers = (
        "最新",
        "今年",
        "现在还",
        "目前",
        "截止",
        "官网",
        "在招",
    )
    _general_knowledge_markers = (
        "是什么",
        "做什么",
        "需要什么",
        "哪些能力",
        "岗位要求",
        "职业路径",
        "发展前景",
    )
    _career_topic_markers = (
        "岗位",
        "职位",
        "职业",
        "工作",
        "求职",
        "面试",
        "简历",
        "产品经理",
        "运营",
        "算法",
        "开发",
    )
    _personalized_intents = frozenset(
        {
            TaskIntent.CAREER_DIRECTION,
            TaskIntent.JOB_COMPARISON,
            TaskIntent.INTERVIEW_REVIEW,
            TaskIntent.OFFER_DECISION,
            TaskIntent.CAREER_PLANNING,
            TaskIntent.PROFILE_UPDATE,
        }
    )
    _cognitive_intents = frozenset(
        {
            TaskIntent.CAREER_DIRECTION,
            TaskIntent.INTERVIEW_REVIEW,
            TaskIntent.OFFER_DECISION,
            TaskIntent.CAREER_PLANNING,
        }
    )
    _knowledge_intents = frozenset(
        {
            TaskIntent.CAREER_DIRECTION,
            TaskIntent.RESUME_REVIEW,
            TaskIntent.RESUME_TAILORING,
            TaskIntent.INTERVIEW_PREPARATION,
            TaskIntent.OFFER_DECISION,
            TaskIntent.CAREER_PLANNING,
        }
    )

    def plan(self, frame: IntentFrame, message: str) -> RetrievalPlan:
        if frame.support_mode is SupportMode.LISTEN:
            return self._listen_plan(frame, message)

        routes: list[RetrievalRoute] = []
        reason_codes: list[str] = []
        has_personal_reference = self._contains_any(
            message, self._personal_reference_markers
        )

        if not frame.forbids_memory and (
            has_personal_reference or frame.primary_intent in self._personalized_intents
        ):
            routes.append(
                RetrievalRoute(
                    RetrievalSource.MEMORY,
                    "补全与当前任务相关的已确认用户事实、偏好和经历",
                )
            )
            reason_codes.append("personal_context_needed")

        if frame.primary_intent in self._cognitive_intents:
            routes.append(
                RetrievalRoute(
                    RetrievalSource.COGNITIVE_STATE,
                    "读取待验证的职业方向、证据关系和开放问题",
                )
            )
            reason_codes.append("cognitive_state_relevant")

        if self._contains_any(message, self._private_document_markers):
            routes.append(
                RetrievalRoute(
                    RetrievalSource.PRIVATE_DOCUMENTS,
                    "任务依赖用户简历、JD、作品集或笔记原文",
                    required=True,
                )
            )
            reason_codes.append("private_documents_requested")

        if frame.primary_intent is TaskIntent.JOB_DISCOVERY:
            routes.append(
                RetrievalRoute(
                    RetrievalSource.JOBS,
                    "查询符合当前槽位和硬约束的岗位",
                    required=True,
                    freshness="current",
                    online_allowed=True,
                )
            )
            reason_codes.append("job_results_required")
        elif frame.primary_intent is TaskIntent.JOB_COMPARISON:
            routes.append(
                RetrievalRoute(
                    RetrievalSource.JOBS,
                    "读取待比较岗位的职责、条件和状态",
                    required=True,
                    freshness="current",
                    online_allowed=True,
                )
            )
            reason_codes.append("job_evidence_required")

        needs_general_knowledge = (
            frame.primary_intent is TaskIntent.GENERAL_QUESTION
            and self._contains_any(message, self._general_knowledge_markers)
            and self._contains_any(message, self._career_topic_markers)
        )
        if frame.primary_intent in self._knowledge_intents or needs_general_knowledge:
            routes.append(
                RetrievalRoute(
                    RetrievalSource.CAREER_KNOWLEDGE,
                    "获取支持当前任务的可溯源职业知识",
                )
            )
            reason_codes.append("career_knowledge_relevant")

        if self._contains_any(message, self._freshness_markers) and any(
            route.source in {RetrievalSource.JOBS, RetrievalSource.CAREER_KNOWLEDGE}
            for route in routes
        ):
            routes.append(
                RetrievalRoute(
                    RetrievalSource.WEB,
                    "本轮明确需要最新外部状态，本地证据不足时联网补查",
                    freshness="current",
                    online_allowed=True,
                )
            )
            reason_codes.append("freshness_requires_online_fallback")

        tool_sources = {
            RetrievalSource.PRIVATE_DOCUMENTS,
            RetrievalSource.CAREER_KNOWLEDGE,
            RetrievalSource.JOBS,
            RetrievalSource.WEB,
        }
        allowed_tools = (
            frozenset({"search_career_knowledge"})
            if any(route.source in tool_sources for route in routes)
            else frozenset()
        )
        return RetrievalPlan(
            routes=tuple(routes),
            allowed_tool_names=allowed_tools,
            reason_codes=tuple(reason_codes) or ("current_context_sufficient",),
        )

    def _listen_plan(self, frame: IntentFrame, message: str) -> RetrievalPlan:
        explicit_personal_reference = self._contains_any(
            message, self._personal_reference_markers
        )
        if frame.forbids_memory or not explicit_personal_reference:
            return RetrievalPlan(reason_codes=("listen_without_retrieval",))
        return RetrievalPlan(
            routes=(
                RetrievalRoute(
                    RetrievalSource.MEMORY,
                    "用户在倾听模式中明确引用历史或请求记忆",
                ),
            ),
            reason_codes=("explicit_memory_reference_in_listen",),
        )

    @staticmethod
    def _contains_any(message: str, markers: tuple[str, ...]) -> bool:
        return any(marker in message for marker in markers)
