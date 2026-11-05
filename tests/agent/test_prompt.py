from careerpilot.agent.prompt import PromptComposer
from careerpilot.context.contracts import IntentFrame, RetrievalPlan, TaskIntent
from careerpilot.memory.base import MemoryContext
from careerpilot.support.policy import SupportPolicy
from careerpilot.support.response_strategy import ResponseStrategyEngine


def _compose(message: str) -> str:
    decision = SupportPolicy().decide(message)
    intent = IntentFrame(support=decision, primary_intent=TaskIntent.GENERAL_QUESTION)
    contract = ResponseStrategyEngine().derive(message, decision, intent.primary_intent)
    return PromptComposer().compose(
        decision,
        MemoryContext(),
        intent=intent,
        retrieval_plan=RetrievalPlan(),
        response_contract=contract,
    )


def test_prompt_places_tentative_interest_contract_near_reply_constraints() -> None:
    prompt = _compose("我有点想做 Agent 后端开发")

    assert "<response_contract>" in prompt
    assert "先映照试探中的兴趣，再陪用户探索兴趣来源" in prompt
    assert "默认写成 2–4 个短段落" in prompt
    assert "整篇最多加粗 1 处" in prompt
    assert "最多提出 1 个问题" in prompt
    assert "禁止：大段职业科普、连续盘问、过早制定计划" in prompt
    assert prompt.index("<response_contract>") > prompt.index("<external_knowledge_policy>")


def test_prompt_activates_cbt_without_turning_it_into_argument() -> None:
    prompt = _compose("我技术太差了，肯定做不了 Agent 后端")

    assert "CBT 引导已启用" in prompt
    assert "区分情境、感受、判断和证据" in prompt
    assert "不要反驳用户" in prompt
    assert "不要把当前判断复述成事实" in prompt
