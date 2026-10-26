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
