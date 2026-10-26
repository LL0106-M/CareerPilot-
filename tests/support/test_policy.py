import pytest

from careerpilot.support.policy import SupportMode, SupportPolicy


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("我现在不想听建议，只想说说今天被拒的感受", SupportMode.LISTEN),
        ("我在产品岗和选调之间很纠结，想看看我更适合什么", SupportMode.EXPLORE),
        ("脑子很乱，帮我把刚才这些想法梳理一下", SupportMode.ORGANIZE),
        ("请帮我创建一个周五复盘的提醒", SupportMode.ACT),
    ],
)
def test_policy_routes_user_intent_without_escalating_to_action(
    message: str, expected: SupportMode
) -> None:
    decision = SupportPolicy().decide(message)

    assert decision.mode is expected
    assert decision.action_tools_allowed is (expected is SupportMode.ACT)


def test_explicit_mode_overrides_heuristics() -> None:
    decision = SupportPolicy().decide(
        "虽然我很焦虑，但现在只需要你听我说，不要安排任务",
        requested_mode=SupportMode.LISTEN,
    )

    assert decision.mode is SupportMode.LISTEN
    assert decision.action_tools_allowed is False
    assert decision.distress_detected is True


def test_safety_risk_overrides_explicit_action_mode() -> None:
    decision = SupportPolicy().decide(
        "我不想活了，帮我安排明天的任务",
        requested_mode=SupportMode.ACT,
    )

    assert decision.mode is SupportMode.LISTEN
    assert decision.distress_detected is True
    assert decision.safety_risk_detected is True
    assert decision.action_tools_allowed is False
