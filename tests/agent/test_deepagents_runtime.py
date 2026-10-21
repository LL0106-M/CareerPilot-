from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from careerpilot.agent.deepagents_runtime import DeepAgentsResponder


class ToolCapableFakeChatModel(FakeMessagesListChatModel):
    bound_tool_names: list[str] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ToolCapableFakeChatModel":
        self.bound_tool_names = [getattr(item, "name", "") for item in tools]
        return self


@pytest.mark.asyncio
async def test_responder_runs_through_a_real_deep_agents_graph() -> None:
    model = ToolCapableFakeChatModel(
        responses=[AIMessage(content="我听见这次拒绝让你很难受，我们先不用急着找原因。")]
    )
    responder = DeepAgentsResponder(model)

    reply = await responder.respond(
        "我被拒了，很难受",
        "先具体慰藉，当前模式为 listen。",
        "thread-1",
    )

    assert reply == "我听见这次拒绝让你很难受，我们先不用急着找原因。"


@pytest.mark.asyncio
async def test_responder_filters_custom_tools_for_each_turn() -> None:
    @tool
    def search_career_knowledge(query: str) -> str:
        """Search the governed CareerPilot knowledge base."""
        return query

    model = ToolCapableFakeChatModel(responses=[AIMessage(content="先听你说。")])
    responder = DeepAgentsResponder(model, tools=[search_career_knowledge])

    await responder.respond(
        "我现在只想说说",
        "当前模式 listen",
        "thread-listen",
        allowed_tool_names=frozenset(),
    )

    assert "search_career_knowledge" not in model.bound_tool_names


@pytest.mark.asyncio
async def test_responder_uses_runtime_tool_instead_of_same_named_static_tool() -> None:
    @tool
    def search_career_knowledge(query: str) -> str:
        """Static search."""
        return f"static:{query}"

    @tool("search_career_knowledge")
    def user_scoped_search(query: str) -> str:
        """User-scoped search."""
        return f"user:{query}"

    model = ToolCapableFakeChatModel(responses=[AIMessage(content="准备好了。")])
    responder = DeepAgentsResponder(model, tools=[search_career_knowledge])

    await responder.respond(
        "根据我的资料准备面试",
        "使用私有资料",
        "thread-private",
        allowed_tool_names=frozenset({"search_career_knowledge"}),
        runtime_tools=(user_scoped_search,),
    )

    assert model.bound_tool_names == ["search_career_knowledge"]
