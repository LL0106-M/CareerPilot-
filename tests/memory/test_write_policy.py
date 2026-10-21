import pytest

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
