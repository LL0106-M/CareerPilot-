import pytest

from careerpilot.memory.models import MemorySensitivity, MemoryType
from careerpilot.memory.write_policy import MemoryWritePolicy


@pytest.mark.parametrize(
    "message",
    [
        "我今天被拒了，真的很难受",
        "我现在特别焦虑，觉得自己什么都做不好",
        "刚才面试完心情很差",
    ],
)
def test_transient_distress_is_not_eligible_for_long_term_memory(message: str) -> None:
    assert MemoryWritePolicy().should_write(message) is False


@pytest.mark.parametrize(
    "message",
    [
        "记住：以后我难受时先听我说，不要马上给计划",
        "我长期更看重可预期的工作节奏",
        "我正在探索国央企的产品和数字化岗位",
        "我的工作地点不能接受离家太远",
    ],
)
def test_explicit_preferences_and_stable_constraints_are_memory_candidates(message: str) -> None:
    assert MemoryWritePolicy().should_write(message) is True


def test_policy_extracts_typed_durable_statement_without_transient_prefix() -> None:
    candidates = MemoryWritePolicy().extract(
        "我今天有点乱。记住：以后我做选择时更看重稳定节奏。"
    )

    assert len(candidates) == 1
    assert candidates[0].type is MemoryType.PREFERENCE
    assert candidates[0].content == "以后我做选择时更看重稳定节奏"
    assert candidates[0].sensitivity is MemorySensitivity.NORMAL
    assert candidates[0].importance == 4


def test_explicit_chat_idea_is_captured_as_an_idea_memory() -> None:
    candidates = MemoryWritePolicy().extract("我的想法是做一个帮助应届生复盘面试的工具。")

    assert len(candidates) == 1
    assert candidates[0].type is MemoryType.IDEA
    assert candidates[0].content == "我的想法是做一个帮助应届生复盘面试的工具"


def test_incidental_wo_you_dian_distress_is_not_a_durable_fact() -> None:
    policy = MemoryWritePolicy()

    assert policy.should_write("我有点焦虑，觉得自己什么都做不好") is False
    assert policy.extract("我有点焦虑，觉得自己什么都做不好") == ()


@pytest.mark.parametrize("prefix", ["更新我的偏好", "修改我的偏好"])
def test_profile_update_wording_creates_a_preference_candidate(prefix: str) -> None:
    candidates = MemoryWritePolicy().extract(f"{prefix}：我现在更喜欢远程工作。")

    assert len(candidates) == 1
    assert candidates[0].type is MemoryType.PREFERENCE
    assert candidates[0].content.endswith("我现在更喜欢远程工作")
