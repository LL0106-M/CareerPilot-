"""Derive answer-shaping controls from the current user turn.

The bounded appraisal and response-control boundary are independently implemented from
concepts documented by ``Elaine-wy/emoai-affect-engine`` (MIT). CareerPilot deliberately
keeps user safety, memory, task authority, and personality outside this module.
"""

from dataclasses import dataclass

from careerpilot.context.contracts import TaskIntent
from careerpilot.support.policy import SupportDecision, SupportMode


@dataclass(frozen=True, slots=True)
class AffectAppraisal:
    valence: str
    intensity: str
    controllability: str
    primary_event: str
    mixed_valence: bool = False


@dataclass(frozen=True, slots=True)
class CBTGuidance:
    active: bool = False
    move: str = "none"
    must_not_dispute: bool = True


@dataclass(frozen=True, slots=True)
class PresentationContract:
    paragraph_range: tuple[int, int] = (2, 4)
    bold_max: int = 1
    max_questions: int = 1
    headings_allowed: bool = True
    prefer_bullets: bool = True


@dataclass(frozen=True, slots=True)
class ResponseContract:
    appraisal: AffectAppraisal
    cbt: CBTGuidance
    response_move: str
    warmth: str
    initiative: str
    verbosity: str
    question_target: str
    avoid: tuple[str, ...]
    presentation: PresentationContract

    _MOVE_LABELS = {
        "reflect_then_explore": "先映照试探中的兴趣，再陪用户探索兴趣来源",
        "acknowledge_then_separate_thought_from_fact": (
            "先接住具体担忧，再温和区分情境、感受、判断与证据"
        ),
        "advance_one_confirmable_action": "只推进一个可确认、低压力的行动",
        "listen_and_reflect": "只倾听并具体复述用户此刻的处境与感受",
        "prioritize_immediate_safety": "先直接表达关切并确认用户是否处于立即危险中",
        "organize_without_overriding": "帮助梳理，但不替用户下结论",
        "explore_without_concluding": "探索可能性与证据，不抢先给出适配结论",
        "answer_compactly": "直接、简短地回应当前表达",
    }
    _AVOID_LABELS = {
        "role_lecture": "大段职业科普",
        "multi_question_intake": "连续盘问",
        "premature_plan": "过早制定计划",
        "forced_positive_reframe": "强行积极改写",
        "diagnosis": "心理诊断",
        "advice": "建议",
        "action_plan": "行动计划",
        "career_analysis": "职业分析",
        "career_planning": "职业规划",
        "tool_use": "调用工具",
    }

    def as_prompt_context(self) -> str:
        move = self._MOVE_LABELS[self.response_move]
        avoid = "、".join(self._AVOID_LABELS.get(item, item) for item in self.avoid)
        presentation = self.presentation
        lines = [
            f"- 本轮回答动作：{move}。",
            (
                "- 表达控制："
                f"warmth={self.warmth}, initiative={self.initiative}, "
                f"verbosity={self.verbosity}。"
            ),
            f"- 追问目标：{self.question_target}；最多提出 {presentation.max_questions} 个问题。",
            (
                f"- 默认写成 {presentation.paragraph_range[0]}–"
                f"{presentation.paragraph_range[1]} 个短段落，段落之间留空行；"
                f"整篇最多加粗 {presentation.bold_max} 处。"
            ),
            self._format_block_style(presentation),
        ]
        if self.cbt.active:
            lines.append(
                "- CBT 引导已启用：区分情境、感受、判断和证据；不要反驳用户，"
                "也不要把当前判断复述成事实。"
            )
        if avoid:
            lines.append(f"- 禁止：{avoid}。")
        return "\n".join(lines)

    @staticmethod
    def _format_block_style(presentation: PresentationContract) -> str:
        bullet_rule = (
            "有两个及以上并列项时才使用项目符号"
            if presentation.prefer_bullets
            else "不要使用项目符号"
        )
        heading_rule = (
            "允许在长回答中使用小标题"
            if presentation.headings_allowed
            else "不要使用小标题"
        )
        return f"- {bullet_rule}；{heading_rule}。"


class ResponseStrategyEngine:
    """Create a conservative, inspectable contract for the next answer."""

    _tentative_interest_markers = (
        "有点想",
        "有些想",
        "想试试",
        "开始想",
        "好像想",
        "可能想",
    )
    _goal_markers = ("做", "学", "转", "尝试", "试试", "方向")
    _absolute_markers = ("肯定", "一定", "完全", "永远", "根本", "注定")
    _negative_judgment_markers = (
        "做不了",
        "不可能",
        "不行",
        "太差",
        "没能力",
        "没用",
        "失败",
    )

    def derive(
        self,
        message: str,
        decision: SupportDecision,
        intent: TaskIntent,
    ) -> ResponseContract:
        text = message.strip()
        if decision.safety_risk_detected:
            return self._safety_contract()
        if decision.mode is SupportMode.ACT:
            return self._action_contract()
        if decision.mode is SupportMode.LISTEN:
            return self._listen_contract(decision)

        has_tentative_interest = self._contains_any(
            text, self._tentative_interest_markers
        ) and self._contains_any(text, self._goal_markers)
        has_automatic_thought = self._contains_any(
            text, self._absolute_markers
        ) and self._contains_any(text, self._negative_judgment_markers)

        if has_automatic_thought:
            return self._cbt_contract()
        if has_tentative_interest:
            return self._tentative_interest_contract()
        if decision.mode is SupportMode.EXPLORE:
            return ResponseContract(
                appraisal=AffectAppraisal("neutral", "low", "medium", "exploration"),
                cbt=CBTGuidance(),
                response_move="explore_without_concluding",
                warmth="medium",
                initiative="low",
                verbosity="short",
                question_target="missing_evidence_or_motivation",
                avoid=("premature_plan",),
                presentation=PresentationContract(),
            )
        if decision.mode is SupportMode.ORGANIZE and intent is not TaskIntent.GENERAL_QUESTION:
            return ResponseContract(
                appraisal=AffectAppraisal("neutral", "low", "medium", "task_clarification"),
                cbt=CBTGuidance(),
                response_move="organize_without_overriding",
                warmth="medium",
                initiative="low",
                verbosity="short",
                question_target="single_missing_fact",
                avoid=("premature_plan",),
                presentation=PresentationContract(),
            )
        return self._neutral_contract()

    def _tentative_interest_contract(self) -> ResponseContract:
        return ResponseContract(
            appraisal=AffectAppraisal("positive", "low", "medium", "goal_emergence"),
            cbt=CBTGuidance(),
            response_move="reflect_then_explore",
            warmth="medium",
            initiative="low",
            verbosity="short",
            question_target="source_of_interest",
            avoid=("role_lecture", "multi_question_intake", "premature_plan"),
            presentation=PresentationContract(),
        )

    def _cbt_contract(self) -> ResponseContract:
        return ResponseContract(
            appraisal=AffectAppraisal("negative", "high", "medium", "goal_block"),
            cbt=CBTGuidance(
                active=True,
                move="separate_situation_feeling_judgment_and_evidence",
            ),
            response_move="acknowledge_then_separate_thought_from_fact",
            warmth="high",
            initiative="low",
            verbosity="short",
            question_target="concrete_blocker",
            avoid=("forced_positive_reframe", "diagnosis", "premature_plan"),
            presentation=PresentationContract(),
        )

    def _action_contract(self) -> ResponseContract:
        return ResponseContract(
            appraisal=AffectAppraisal("neutral", "low", "high", "goal_progress"),
            cbt=CBTGuidance(),
            response_move="advance_one_confirmable_action",
            warmth="medium",
            initiative="medium",
            verbosity="short",
            question_target="confirmation_only_if_required",
            avoid=("multi_question_intake",),
            presentation=PresentationContract(),
        )

    def _listen_contract(self, decision: SupportDecision) -> ResponseContract:
        return ResponseContract(
            appraisal=AffectAppraisal(
                "negative" if decision.distress_detected else "neutral",
                "high" if decision.distress_detected else "low",
                "low",
                "distress" if decision.distress_detected else "sharing",
            ),
            cbt=CBTGuidance(),
            response_move="listen_and_reflect",
            warmth="high",
            initiative="none",
            verbosity="short",
            question_target="felt_experience_if_helpful",
            avoid=("advice", "action_plan", "multi_question_intake"),
            presentation=PresentationContract(
                headings_allowed=False,
                prefer_bullets=False,
            ),
        )

    def _safety_contract(self) -> ResponseContract:
        return ResponseContract(
            appraisal=AffectAppraisal("negative", "high", "low", "safety_risk"),
            cbt=CBTGuidance(),
            response_move="prioritize_immediate_safety",
            warmth="high",
            initiative="medium",
            verbosity="short",
            question_target="immediate_danger",
            avoid=("career_analysis", "career_planning", "tool_use"),
            presentation=PresentationContract(
                headings_allowed=False,
                prefer_bullets=False,
            ),
        )

    def _neutral_contract(self) -> ResponseContract:
        return ResponseContract(
            appraisal=AffectAppraisal("neutral", "low", "medium", "neutral"),
            cbt=CBTGuidance(),
            response_move="answer_compactly",
            warmth="medium",
            initiative="low",
            verbosity="short",
            question_target="none",
            avoid=("multi_question_intake",),
            presentation=PresentationContract(),
        )

    @staticmethod
    def _contains_any(message: str, markers: tuple[str, ...]) -> bool:
        return any(marker in message for marker in markers)
