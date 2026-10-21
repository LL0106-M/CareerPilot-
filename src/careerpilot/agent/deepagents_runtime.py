from typing import Any

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

from careerpilot.agent.base import AgentResponder

_BUILT_IN_TOOLS = frozenset(
    {"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute", "task"}
)


def register_careerpilot_openai_profile() -> None:
    """Keep the first MVP single-agent and unable to access generic host tools."""

    register_harness_profile(
        "openai",
        HarnessProfile(
            excluded_tools=_BUILT_IN_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )


class DeepAgentsResponder(AgentResponder):
    def __init__(self, model: BaseChatModel, tools: list[BaseTool] | None = None) -> None:
        register_careerpilot_openai_profile()
        self._model = model
        self._tools = tuple(tools or ())
        self._checkpointer = InMemorySaver()

    async def respond(
        self,
        user_message: str,
        system_context: str,
        thread_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools: tuple[BaseTool, ...] = (),
    ) -> str:
        tools_by_name = {tool.name: tool for tool in self._tools}
        tools_by_name.update({tool.name: tool for tool in runtime_tools})
        tools = tuple(tools_by_name.values())
        if allowed_tool_names is not None:
            tools = tuple(tool for tool in tools if tool.name in allowed_tool_names)
        graph = create_deep_agent(
            model=self._model,
            tools=list(tools),
            system_prompt=system_context,
            # Deep Agents requires read_file as harness scaffolding. With the default
            # StateBackend it can only read files supplied in graph state, not the host.
            middleware=[FilesystemMiddleware(tools=["read_file"])],
            subagents=[],
            checkpointer=self._checkpointer,
            name="careerpilot",
        )
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        messages = result.get("messages", [])
        if not messages or not isinstance(messages[-1], AIMessage):
            raise RuntimeError("Deep Agents returned no assistant message")
        text = _message_text(messages[-1].content)
        if not text:
            raise RuntimeError("Deep Agents returned an empty assistant message")
        return text


def _message_text(content: str | list[str | dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()
