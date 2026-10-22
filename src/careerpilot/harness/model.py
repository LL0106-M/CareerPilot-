from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from careerpilot.harness.contracts import (
    HarnessMessage,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ToolCall,
)


class LangChainModelGateway(ModelGateway):
    """Temporary provider adapter while CareerPilot owns the orchestration loop."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def generate(self, request: ModelRequest) -> ModelResponse:
        message = await self._configured_model(request).ainvoke(
            [_to_provider_message(item) for item in request.messages]
        )
        return _to_model_response(message)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        accumulated = None
        async for chunk in self._configured_model(request).astream(
            [_to_provider_message(item) for item in request.messages]
        ):
            if not isinstance(chunk, AIMessage):
                raise RuntimeError("Model provider returned a non-assistant message")
            accumulated = chunk if accumulated is None else accumulated + chunk
            text = _message_text(chunk.content, strip=False)
            if text:
                yield ModelStreamEvent(text_delta=text)
        if accumulated is None:
            raise RuntimeError("Model provider returned an empty stream")
        yield ModelStreamEvent(response=_to_model_response(accumulated))

    def _configured_model(self, request: ModelRequest) -> BaseChatModel:
        model = self._model
        if request.tools:
            model = model.bind_tools([_tool_schema(item) for item in request.tools])
        return model


def _to_model_response(message: AIMessage) -> ModelResponse:
    if not isinstance(message, AIMessage):
        raise RuntimeError("Model provider returned a non-assistant message")
    calls = tuple(
        ToolCall(
            id=str(item.get("id") or f"call-{index}"),
            name=str(item.get("name") or ""),
            arguments=dict(item.get("args") or {}),
        )
        for index, item in enumerate(message.tool_calls)
    )
    metadata = message.usage_metadata or {}
    usage = {
        key: int(value)
        for key, value in metadata.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    return ModelResponse(
        text=_message_text(message.content),
        tool_calls=calls,
        finish_reason=message.response_metadata.get("finish_reason"),
        usage=usage,
    )


def _tool_schema(tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_provider_message(message: HarnessMessage) -> BaseMessage:
    if message.role == "system":
        return SystemMessage(content=message.content)
    if message.role == "user":
        return HumanMessage(content=message.content)
    if message.role == "assistant":
        return AIMessage(
            content=message.content,
            tool_calls=[
                {"id": call.id, "name": call.name, "args": call.arguments, "type": "tool_call"}
                for call in message.tool_calls
            ],
        )
    if message.role == "tool" and message.tool_call_id is not None:
        return ToolMessage(
            content=message.content,
            tool_call_id=message.tool_call_id,
            name=message.name,
        )
    raise ValueError(f"Unsupported harness message role: {message.role}")


def _message_text(
    content: str | list[str | dict[str, Any]], *, strip: bool = True
) -> str:
    if isinstance(content, str):
        return content.strip() if strip else content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    text = "\n".join(parts)
    return text.strip() if strip else text
