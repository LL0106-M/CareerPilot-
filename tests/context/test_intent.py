import pytest

from careerpilot.context.contracts import TaskIntent
from careerpilot.context.intent import RuleBasedIntentInterpreter
from careerpilot.support.policy import SupportMode


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("我被拒了，现在只想说说", TaskIntent.EMOTIONAL_SUPPORT),
        ("帮我看看上海还有哪些 AI 产品岗位", TaskIntent.JOB_DISCOVERY),
        ("比较一下这两个岗位", TaskIntent.JOB_COMPARISON),
        ("看看我的简历有什么问题", TaskIntent.RESUME_REVIEW),
        ("根据这个 JD 改写我的简历", TaskIntent.RESUME_TAILORING),
        ("下周腾讯产品二面，帮我准备", TaskIntent.INTERVIEW_PREPARATION),
        ("帮我复盘刚才的二面", TaskIntent.INTERVIEW_REVIEW),
        ("两个 offer 应该怎么选", TaskIntent.OFFER_DECISION),
        ("我适合什么职业方向", TaskIntent.CAREER_DIRECTION),
        ("帮我做一个未来三个月的求职计划", TaskIntent.CAREER_PLANNING),
        ("记住，以后只考虑上海", TaskIntent.PROFILE_UPDATE),
        ("产品经理一般需要哪些能力", TaskIntent.GENERAL_QUESTION),
    ],
)
async def test_interpreter_classifies_p0_task_intents(
    message: str, expected: TaskIntent
) -> None:
    frame = await RuleBasedIntentInterpreter().interpret(message)

    assert frame.primary_intent is expected


async def test_interpreter_keeps_emotion_as_secondary_when_task_is_explicit() -> None:
    frame = await RuleBasedIntentInterpreter().interpret(
        "二面失败让我很难受，但帮我准备明天的产品面试"
    )

    assert frame.primary_intent is TaskIntent.INTERVIEW_PREPARATION
    assert frame.secondary_intents == (TaskIntent.EMOTIONAL_SUPPORT,)


async def test_interpreter_extracts_current_task_slots() -> None:
    frame = await RuleBasedIntentInterpreter().interpret(
        "帮我看看上海和杭州的校招产品经理岗位"
    )

    assert frame.slot("locations").values == ("上海", "杭州")
    assert frame.slot("career_stage").values == ("campus",)
    assert frame.slot("role_families").values == ("product",)


async def test_explicit_mode_remains_authoritative() -> None:
    frame = await RuleBasedIntentInterpreter().interpret(
        "帮我看看还有哪些岗位",
        requested_mode=SupportMode.LISTEN,
    )

    assert frame.support_mode is SupportMode.LISTEN
    assert frame.primary_intent is TaskIntent.JOB_DISCOVERY
