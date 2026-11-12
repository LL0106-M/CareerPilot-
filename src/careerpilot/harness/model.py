import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import APIError, AsyncOpenAI

from careerpilot.harness.contracts import (
    HarnessMessage,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ToolCall,
    ToolSchema,
)
from careerpilot.harness.errors import sanitize_provider_error


@dataclass(slots=True)
class _StreamedToolCall:
    id: str = ""
    name: str = ""
    arguments: str = ""


class OpenAICompatibleModelGateway(ModelGateway):
    """Provider-neutral gateway backed by an OpenAI-compatible chat API."""

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str,
        temperature: float,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    async def generate(self, request: ModelRequest) -> ModelResponse:
        try:
            completion = await self._client.chat.completions.create(
                **self._request_arguments(request, stream=False)
            )
        except APIError as exc:
            raise sanitize_provider_error(exc) from None
        choices = getattr(completion, "choices", ())
        if not choices:
            raise RuntimeError("Model provider returned no choices")
        choice = choices[0]
        message = choice.message
        return ModelResponse(
            text=_message_text(getattr(message, "content", None)),
            tool_calls=tuple(
                _normalize_tool_call(item, index)
                for index, item in enumerate(getattr(message, "tool_calls", None) or ())
            ),
            finish_reason=getattr(choice, "finish_reason", None),
            usage=_normalize_usage(getattr(completion, "usage", None)),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        text_parts: list[str] = []
        calls: dict[int, _StreamedToolCall] = {}
        finish_reason: str | None = None
        usage: dict[str, int] = {}
        received_chunk = False

        try:
            stream = await self._client.chat.completions.create(
                **self._request_arguments(request, stream=True)
            )
            async for chunk in stream:
                received_chunk = True
                current_usage = _normalize_usage(getattr(chunk, "usage", None))
                if current_usage:
                    usage = current_usage
                choices = getattr(chunk, "choices", ())
                if not choices:
                    continue
                choice = choices[0]
                if getattr(choice, "finish_reason", None) is not None:
                    finish_reason = choice.finish_reason
                delta = choice.delta
                text = _message_text(getattr(delta, "content", None), strip=False)
                if text:
                    text_parts.append(text)
                    yield ModelStreamEvent(text_delta=text)
                for fragment in getattr(delta, "tool_calls", None) or ():
                    index = getattr(fragment, "index", None)
                    if not isinstance(index, int) or isinstance(index, bool):
                        raise ValueError("Streamed tool call is missing a numeric index")
                    accumulated = calls.setdefault(index, _StreamedToolCall())
                    fragment_id = getattr(fragment, "id", None)
                    if fragment_id:
                        accumulated.id += str(fragment_id)
                    function = getattr(fragment, "function", None)
                    if function is not None:
                        name = getattr(function, "name", None)
                        arguments = getattr(function, "arguments", None)
                        if name:
                            accumulated.name += str(name)
                        if arguments:
                            accumulated.arguments += str(arguments)
        except APIError as exc:
            raise sanitize_provider_error(exc) from None

        if not received_chunk:
            raise RuntimeError("Model provider returned an empty stream")
        tool_calls = tuple(
            ToolCall(
                id=item.id or f"call-{index}",
                name=_require_tool_name(item.name),
                arguments=_parse_tool_arguments(item.arguments),
            )
            for index, item in sorted(calls.items())
        )
        yield ModelStreamEvent(
            response=ModelResponse(
                text="".join(text_parts).strip(),
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )
        )

    def _request_arguments(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "model": self._model,
            "messages": [_to_provider_message(item) for item in request.messages],
            "temperature": self._temperature,
            "stream": stream,
        }
        if request.tools:
            arguments["tools"] = [_tool_schema(item) for item in request.tools]
        return arguments


def _normalize_tool_call(item: Any, index: int) -> ToolCall:
    function = getattr(item, "function", None)
    if function is None:
        raise ValueError("Model provider returned a tool call without a function")
    return ToolCall(
        id=str(getattr(item, "id", None) or f"call-{index}"),
        name=_require_tool_name(getattr(function, "name", None)),
        arguments=_parse_tool_arguments(getattr(function, "arguments", "")),
    )


def _require_tool_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Model provider returned a tool call without a function name")
    return value


def _parse_tool_arguments(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Tool call arguments must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Tool call arguments must be a JSON object")
    return parsed


def _normalize_usage(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    mapping = {
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }
    return {
        key: value
        for key, value in mapping.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }


def _tool_schema(tool: ToolSchema) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _to_provider_message(message: HarnessMessage) -> dict[str, Any]:
    if message.role in {"system", "user"}:
        return {"role": message.role, "content": message.content}
    if message.role == "assistant":
        payload: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or None,
        }
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        return payload
    if message.role == "tool" and message.tool_call_id is not None:
        return {
            "role": "tool",
            "content": message.content,
            "tool_call_id": message.tool_call_id,
        }
    raise ValueError(f"Unsupported harness message role: {message.role}")


def _message_text(content: Any, *, strip: bool = True) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip() if strip else content
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
    text = "\n".join(parts)
    return text.strip() if strip else text
