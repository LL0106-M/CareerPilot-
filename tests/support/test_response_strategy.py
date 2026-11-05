import pytest

from careerpilot.context.contracts import TaskIntent
from careerpilot.support.policy import SupportMode, SupportPolicy
from careerpilot.support.response_strategy import ResponseStrategyEngine


@pytest.fixture
def engine() -> ResponseStrategyEngine:
    return ResponseStrategyEngine()


def test_tentative_interest_reflects_before_exploring(engine: ResponseStrategyEngine) -> None:
    decision = SupportPolicy().decide("我有点想做 Agent 后端开发")

    contract = engine.derive(
        "我有点想做 Agent 后端开发",
        decision,
        TaskIntent.GENERAL_QUESTION,
    )

    assert contract.appraisal.primary_event == "goal_emergence"
    assert contract.cbt.active is False
    assert contract.response_move == "reflect_then_explore"
    assert contract.initiative == "low"
    assert contract.verbosity == "short"
    assert contract.question_target == "source_of_interest"
    assert "role_lecture" in contract.avoid
    assert "multi_question_intake" in contract.avoid
    assert contract.presentation.paragraph_range == (2, 4)
    assert contract.presentation.bold_max == 1
    assert contract.presentation.max_questions == 1


def test_negative_absolute_self_judgment_activates_cbt_decoupling(
    engine: ResponseStrategyEngine,
) -> None:
    decision = SupportPolicy().decide("我技术太差了，肯定做不了 Agent 后端")

    contract = engine.derive(
        "我技术太差了，肯定做不了 Agent 后端",
        decision,
        TaskIntent.GENERAL_QUESTION,
    )

    assert contract.appraisal.primary_event == "goal_block"
    assert contract.cbt.active is True
    assert contract.cbt.move == "separate_situation_feeling_judgment_and_evidence"
    assert contract.cbt.must_not_dispute is True
    assert contract.response_move == "acknowledge_then_separate_thought_from_fact"
    assert contract.warmth == "high"
    assert contract.question_target == "concrete_blocker"
    assert "forced_positive_reframe" in contract.avoid


def test_explicit_action_mode_keeps_action_as_the_response_move(
    engine: ResponseStrategyEngine,
) -> None:
    decision = SupportPolicy().decide("帮我创建一个明晚学习 Agent 后端的提醒")

    contract = engine.derive(
        "帮我创建一个明晚学习 Agent 后端的提醒",
        decision,
        TaskIntent.CALENDAR_MANAGEMENT,
    )

    assert decision.mode is SupportMode.ACT
    assert contract.response_move == "advance_one_confirmable_action"
    assert contract.initiative == "medium"
    assert contract.cbt.active is False
    assert contract.question_target == "confirmation_only_if_required"


def test_listen_mode_avoids_report_format_and_problem_solving(
    engine: ResponseStrategyEngine,
) -> None:
    decision = SupportPolicy().decide("刚收到拒信，我很难受，只想说说，不要建议")

    contract = engine.derive(
        "刚收到拒信，我很难受，只想说说，不要建议",
        decision,
        TaskIntent.EMOTIONAL_SUPPORT,
    )

    assert contract.response_move == "listen_and_reflect"
    assert contract.warmth == "high"
    assert contract.initiative == "none"
    assert contract.presentation.headings_allowed is False
    assert contract.presentation.prefer_bullets is False
    assert "advice" in contract.avoid
    assert "action_plan" in contract.avoid


def test_safety_risk_keeps_crisis_support_available(
    engine: ResponseStrategyEngine,
) -> None:
    decision = SupportPolicy().decide("我彻底绝望了，现在不想活了")

    contract = engine.derive(
        "我彻底绝望了，现在不想活了",
        decision,
        TaskIntent.EMOTIONAL_SUPPORT,
    )

    assert decision.safety_risk_detected is True
    assert contract.response_move == "prioritize_immediate_safety"
    assert contract.question_target == "immediate_danger"
    assert "advice" not in contract.avoid
    assert "career_analysis" in contract.avoid


def test_empty_neutral_turn_gets_a_compact_safe_default(
    engine: ResponseStrategyEngine,
) -> None:
    decision = SupportPolicy().decide("")

    contract = engine.derive("", decision, TaskIntent.GENERAL_QUESTION)

    assert contract.appraisal.primary_event == "neutral"
    assert contract.response_move == "answer_compactly"
    assert contract.verbosity == "short"
    assert contract.question_target == "none"
    assert contract.presentation.max_questions == 1


def test_prompt_context_turns_strategy_into_model_instructions(
    engine: ResponseStrategyEngine,
) -> None:
    decision = SupportPolicy().decide("我有点想做 Agent 后端开发")
    contract = engine.derive(
        "我有点想做 Agent 后端开发",
        decision,
        TaskIntent.GENERAL_QUESTION,
    )

    context = contract.as_prompt_context()

    assert "先映照试探中的兴趣，再陪用户探索兴趣来源" in context
    assert "默认写成 2–4 个短段落" in context
    assert "整篇最多加粗 1 处" in context
    assert "最多提出 1 个问题" in context
    assert "禁止：大段职业科普、连续盘问、过早制定计划" in context


def test_listen_prompt_context_suppresses_bullets(
    engine: ResponseStrategyEngine,
) -> None:
    decision = SupportPolicy().decide("刚收到拒信，我很难受，只想说说，不要建议")
    contract = engine.derive(
        "刚收到拒信，我很难受，只想说说，不要建议",
        decision,
        TaskIntent.EMOTIONAL_SUPPORT,
    )

    context = contract.as_prompt_context()

    assert "不要使用项目符号" in context
    assert "不要使用小标题" in context
