from careerpilot.context.contracts import (
    IntentConfidence,
    IntentFrame,
    IntentSlot,
    TaskIntent,
)
from careerpilot.support.policy import SupportMode, SupportPolicy


class RuleBasedIntentInterpreter:
    """Deterministic P0 baseline behind the future semantic classifier port."""

    _no_memory_markers = (
        "不要参考以前",
        "别参考以前",
        "不要用历史",
        "不用之前的信息",
        "忘掉之前",
    )
    _profile_markers = (
        "记住",
        "以后都",
        "我长期",
        "更正一下",
        "更新我的",
        "修改我的偏好",
    )
    _resume_markers = ("简历", "履历", "cv", "CV")
    _tailoring_markers = ("改写", "修改", "优化", "润色", "针对", "匹配")
    _review_markers = ("看看", "问题", "诊断", "哪里", "评估", "分析")
    _interview_markers = ("面试", "一面", "二面", "三面", "业务面", "HR面", "hr面")
    _preparation_markers = ("准备", "怎么准备", "模拟", "题目", "练习")
    _reflection_markers = ("复盘", "回顾", "表现", "哪里没答好")
    _job_markers = ("岗位", "职位", "招聘", "在招", "投递", "工作机会")
    _discovery_markers = ("找", "看看", "有哪些", "推荐", "搜", "查询")
    _comparison_markers = ("比较", "对比", "怎么选", "哪个好", "选择")
    _offer_markers = ("offer", "Offer", "录用", "口头 offer", "口头Offer")
    _direction_markers = (
        "职业方向",
        "方向",
        "探索",
        "适合什么",
        "更适合",
        "转行",
        "发展方向",
    )
    _planning_markers = ("规划", "计划", "未来三个月", "秋招计划", "求职计划")
    _knowledge_markers = ("是什么", "做什么", "需要什么", "哪些能力", "要求")

    _locations = (
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州",
        "南京",
        "苏州",
        "成都",
        "武汉",
        "西安",
        "重庆",
    )
    _career_stages = {
        "校招": "campus",
        "秋招": "campus",
        "春招": "campus",
        "应届": "campus",
        "社招": "experienced",
        "转行": "career_change",
        "实习": "internship",
    }
    _role_families = {
        "产品经理": "product",
        "产品岗": "product",
        "产品运营": "product_operations",
        "运营": "operations",
        "算法": "algorithm",
        "开发": "engineering",
        "数据分析": "data",
        "咨询": "consulting",
    }

    def __init__(self, support_policy: SupportPolicy | None = None) -> None:
        self._support_policy = support_policy or SupportPolicy()

    async def interpret(
        self,
        message: str,
        requested_mode: SupportMode | None = None,
    ) -> IntentFrame:
        support = self._support_policy.decide(message, requested_mode)
        primary, reason = self._classify(message, support.mode)
        secondary = (
            (TaskIntent.EMOTIONAL_SUPPORT,)
            if support.distress_detected and primary is not TaskIntent.EMOTIONAL_SUPPORT
            else ()
        )
        return IntentFrame(
            support=support,
            primary_intent=primary,
            secondary_intents=secondary,
            slots=self._extract_slots(message),
            confidence=(
                IntentConfidence.MEDIUM
                if primary is TaskIntent.GENERAL_QUESTION
                else IntentConfidence.HIGH
            ),
            reason_codes=(reason,),
            forbids_memory=self._contains_any(message, self._no_memory_markers),
        )

    def _classify(
        self, message: str, support_mode: SupportMode
    ) -> tuple[TaskIntent, str]:
        has_resume = self._contains_any(message, self._resume_markers)
        has_interview = self._contains_any(message, self._interview_markers)
        has_job = self._contains_any(message, self._job_markers)

        if self._contains_any(message, self._profile_markers):
            return TaskIntent.PROFILE_UPDATE, "explicit_profile_or_memory_update"
        if has_resume and self._contains_any(message, self._tailoring_markers):
            return TaskIntent.RESUME_TAILORING, "resume_change_requested"
        if has_resume and self._contains_any(message, self._review_markers):
            return TaskIntent.RESUME_REVIEW, "resume_review_requested"
        if has_interview and self._contains_any(message, self._reflection_markers):
            return TaskIntent.INTERVIEW_REVIEW, "interview_reflection_requested"
        if has_interview and self._contains_any(message, self._preparation_markers):
            return TaskIntent.INTERVIEW_PREPARATION, "interview_preparation_requested"
        if self._contains_any(message, self._offer_markers) and self._contains_any(
            message, self._comparison_markers
        ):
            return TaskIntent.OFFER_DECISION, "offer_decision_requested"
        if has_job and self._contains_any(message, self._comparison_markers):
            return TaskIntent.JOB_COMPARISON, "job_comparison_requested"
        if has_job and self._contains_any(message, self._discovery_markers):
            return TaskIntent.JOB_DISCOVERY, "job_discovery_requested"
        if self._contains_any(message, self._planning_markers):
            return TaskIntent.CAREER_PLANNING, "career_plan_requested"
        if self._contains_any(message, self._direction_markers):
            return TaskIntent.CAREER_DIRECTION, "career_direction_requested"
        if support_mode is SupportMode.LISTEN:
            return TaskIntent.EMOTIONAL_SUPPORT, "support_mode_listen"
        if self._contains_any(message, self._knowledge_markers):
            return TaskIntent.GENERAL_QUESTION, "general_career_question"
        return TaskIntent.GENERAL_QUESTION, "fallback_general_question"

    def _extract_slots(self, message: str) -> tuple[IntentSlot, ...]:
        slots: list[IntentSlot] = []
        locations = tuple(location for location in self._locations if location in message)
        if locations:
            slots.append(IntentSlot("locations", locations))

        stages = tuple(
            dict.fromkeys(
                value for marker, value in self._career_stages.items() if marker in message
            )
        )
        if stages:
            slots.append(IntentSlot("career_stage", stages))

        roles = tuple(
            dict.fromkeys(
                value for marker, value in self._role_families.items() if marker in message
            )
        )
        if roles:
            slots.append(IntentSlot("role_families", roles))
        return tuple(slots)

    @staticmethod
    def _contains_any(message: str, markers: tuple[str, ...]) -> bool:
        return any(marker in message for marker in markers)
