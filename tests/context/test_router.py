import pytest

from careerpilot.context.contracts import RetrievalSource
from careerpilot.context.intent import RuleBasedIntentInterpreter
from careerpilot.context.router import IntentAwareRetrievalRouter


async def _plan(message: str):
    frame = await RuleBasedIntentInterpreter().interpret(message)
    return IntentAwareRetrievalRouter().plan(frame, message)


@pytest.mark.asyncio
async def test_listen_mode_uses_no_retrieval_by_default() -> None:
    plan = await _plan("我今天被拒了，很难受，现在只想说说")

    assert plan.routes == ()
    assert plan.allowed_tool_names == frozenset()


@pytest.mark.asyncio
async def test_explicit_history_reference_can_retrieve_memory_without_tools() -> None:
    plan = await _plan("按照我之前说的情况来，但现在先听我说")

    assert plan.uses(RetrievalSource.MEMORY)
    assert plan.allowed_tool_names == frozenset()


@pytest.mark.asyncio
async def test_general_knowledge_uses_rag_without_personal_memory() -> None:
    plan = await _plan("产品经理一般需要哪些能力？")

    assert not plan.uses(RetrievalSource.MEMORY)
    assert plan.uses(RetrievalSource.CAREER_KNOWLEDGE)
    assert plan.allowed_tool_names == frozenset({"search_career_knowledge"})


@pytest.mark.asyncio
async def test_context_sufficient_fallback_does_not_retrieve() -> None:
    plan = await _plan("只回复 ROUTER_OK")

    assert plan.routes == ()
    assert plan.reason_codes == ("current_context_sufficient",)


@pytest.mark.asyncio
async def test_personalized_interview_preparation_uses_memory_private_and_public_rag() -> None:
    plan = await _plan("根据我的简历准备腾讯产品二面")

    assert plan.uses(RetrievalSource.MEMORY)
    assert plan.uses(RetrievalSource.PRIVATE_DOCUMENTS)
    assert plan.uses(RetrievalSource.CAREER_KNOWLEDGE)


@pytest.mark.asyncio
async def test_current_job_search_allows_online_fallback() -> None:
    plan = await _plan("帮我看看今年上海还有哪些在招的 AI 产品岗位")

    assert plan.uses(RetrievalSource.JOBS)
    assert plan.uses(RetrievalSource.WEB)
    assert plan.route_for(RetrievalSource.JOBS).freshness == "current"


@pytest.mark.asyncio
async def test_user_can_forbid_memory_retrieval() -> None:
    plan = await _plan("不要参考以前，帮我规划接下来三个月的求职准备")

    assert not plan.uses(RetrievalSource.MEMORY)
    assert plan.uses(RetrievalSource.COGNITIVE_STATE)
