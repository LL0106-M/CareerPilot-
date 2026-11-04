import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from careerpilot.memory.direction_signals import (
    DirectionExplicitness,
    DirectionSignalAction,
    JsonDirectionSignalDetector,
)


@pytest.mark.asyncio
async def test_detector_parses_explicit_direction_signal() -> None:
    model = FakeMessagesListChatModel(
        responses=[AIMessage(content=(
            '{"explicitness":"explicit","label":"用户表达的方向",'
            '"source_quote":"我想投递这个方向的岗位",'
            '"reason":"用户明确表达了投递意愿",'
            '"confidence":0.98,"suggested_action":"add_to_compass"}'
        ))]
    )

    signal = await JsonDirectionSignalDetector(model).analyze(
        "我想投递这个方向的岗位", "我们可以先梳理岗位要求。"
    )

    assert signal.explicitness is DirectionExplicitness.EXPLICIT
    assert signal.action is DirectionSignalAction.ADD_TO_COMPASS
    assert signal.label == "用户表达的方向"
    assert signal.source_quote == "我想投递这个方向的岗位"
    assert signal.confidence == pytest.approx(0.98)


@pytest.mark.asyncio
async def test_detector_parses_implicit_direction_signal() -> None:
    model = FakeMessagesListChatModel(
        responses=[AIMessage(content=(
            '{"explicitness":"implicit","label":"平台型产品工作",'
            '"source_quote":"最近总是在关注平台型产品",'
            '"reason":"表达了持续关注但没有确认选择",'
            '"confidence":0.76,"suggested_action":"ask_to_add"}'
        ))]
    )

    signal = await JsonDirectionSignalDetector(model).analyze(
        "最近总是在关注平台型产品", "这可能是一条值得留意的线索。"
    )

    assert signal.explicitness is DirectionExplicitness.IMPLICIT
    assert signal.action is DirectionSignalAction.ASK_TO_ADD
    assert signal.label == "平台型产品工作"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["not json", "[]", '{"explicitness":"explicit"}'])
async def test_detector_degrades_malformed_output_to_none(content: str) -> None:
    model = FakeMessagesListChatModel(responses=[AIMessage(content=content)])

    signal = await JsonDirectionSignalDetector(model).analyze("随便聊聊", "好。")

    assert signal.explicitness is DirectionExplicitness.NONE
    assert signal.action is DirectionSignalAction.NONE
    assert signal.label is None


@pytest.mark.asyncio
async def test_detector_accepts_explicit_no_signal_json() -> None:
    model = FakeMessagesListChatModel(
        responses=[AIMessage(content=(
            '{"explicitness":"none","label":null,"source_quote":null,'
            '"reason":"没有职业方向信号","confidence":0.99,'
            '"suggested_action":"none"}'
        ))]
    )

    signal = await JsonDirectionSignalDetector(model).analyze("今天天气不错", "是的。")

    assert signal.explicitness is DirectionExplicitness.NONE
    assert signal.action is DirectionSignalAction.NONE


@pytest.mark.asyncio
async def test_detector_degrades_model_failure_to_none() -> None:
    class FailingModel:
        async def ainvoke(self, _messages):
            raise RuntimeError("model unavailable")

    signal = await JsonDirectionSignalDetector(FailingModel()).analyze("一条消息", "回复")

    assert signal.explicitness is DirectionExplicitness.NONE
    assert signal.action is DirectionSignalAction.NONE
