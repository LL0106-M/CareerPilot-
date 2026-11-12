import json
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from openai import APIStatusError

from careerpilot.harness.contracts import (
    HarnessMessage,
    ModelRequest,
    ToolCall,
    ToolSchema,
)
from careerpilot.harness.errors import ModelProviderError
from careerpilot.harness.model import OpenAICompatibleModelGateway


def _namespace(**values: Any) -> SimpleNamespace:
    return SimpleNamespace(**values)


def _tool_call(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    return _namespace(
        id=call_id,
        function=_namespace(name=name, arguments=arguments),
    )


def _completion(
    *,
    text: str | None = None,
    tool_calls: list[SimpleNamespace] | None = None,
    finish_reason: str | None = "stop",
    usage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return _namespace(
        choices=[
            _namespace(
                message=_namespace(content=text, tool_calls=tool_calls or []),
                finish_reason=finish_reason,
            )
        ],
        usage=usage,
    )


def _chunk(
    *,
    text: str | None = None,
    tool_calls: list[SimpleNamespace] | None = None,
    finish_reason: str | None = None,
    usage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return _namespace(
        choices=[
            _namespace(
                delta=_namespace(content=text, tool_calls=tool_calls or []),
                finish_reason=finish_reason,
            )
        ],
        usage=usage,
    )


class FakeCompletions:
    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        if kwargs.get("stream"):
            async def events():
                for item in result:
                    if isinstance(item, BaseException):
                        raise item
                    yield item

            return events()
        return result


class FakeClient:
    def __init__(self, results: list[Any]) -> None:
        self.completions = FakeCompletions(results)
        self.chat = _namespace(completions=self.completions)


def _gateway(*results: Any) -> tuple[OpenAICompatibleModelGateway, FakeClient]:
    client = FakeClient(list(results))
    return (
        OpenAICompatibleModelGateway(client, model="test-model", temperature=0.2),
        client,
    )


@pytest.mark.asyncio
async def test_generate_normalizes_messages_tools_usage_and_tool_calls() -> None:
    gateway, client = _gateway(
        _completion(
            text="先查一下。",
            tool_calls=[
                _tool_call("call-1", "search", json.dumps({"query": "产品经理"})),
                _tool_call("call-2", "lookup", json.dumps({"id": 7})),
            ],
            finish_reason="tool_calls",
            usage=_namespace(prompt_tokens=11, completion_tokens=5, total_tokens=16),
        )
    )
    request = ModelRequest(
        messages=(
            HarnessMessage(role="system", content="be useful"),
            HarnessMessage(role="user", content="hello"),
            HarnessMessage(
                role="assistant",
                tool_calls=(ToolCall("old-call", "search", {"query": "old"}),),
            ),
            HarnessMessage(
                role="tool",
                content='{"ok": true}',
                tool_call_id="old-call",
                name="search",
            ),
        ),
        tools=(
            ToolSchema(
                name="search",
                description="Search",
                parameters={"type": "object", "properties": {}},
            ),
        ),
    )

    response = await gateway.generate(request)

    assert response.text == "先查一下。"
    assert response.tool_calls == (
        ToolCall("call-1", "search", {"query": "产品经理"}),
        ToolCall("call-2", "lookup", {"id": 7}),
    )
    assert response.finish_reason == "tool_calls"
    assert response.usage == {
        "input_tokens": 11,
        "output_tokens": 5,
        "total_tokens": 16,
    }
    call = client.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["temperature"] == 0.2
    assert call["stream"] is False
    assert call["messages"][2]["tool_calls"][0]["function"]["arguments"] == (
        '{"query": "old"}'
    )
    assert call["messages"][3]["tool_call_id"] == "old-call"
    assert call["tools"][0]["function"]["name"] == "search"


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ["not-json", "[]", '"scalar"'])
async def test_generate_rejects_invalid_or_non_object_tool_arguments(arguments: str) -> None:
    gateway, _ = _gateway(
        _completion(tool_calls=[_tool_call("call-1", "search", arguments)])
    )

    with pytest.raises(ValueError, match="Tool call arguments"):
        await gateway.generate(ModelRequest(messages=()))


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [None, "", " "])
async def test_generate_rejects_missing_or_empty_tool_name(name: str | None) -> None:
    gateway, _ = _gateway(
        _completion(tool_calls=[_tool_call("call-1", name, '{"query":"x"}')])
    )

    with pytest.raises(ValueError, match="tool call without a function name"):
        await gateway.generate(ModelRequest(messages=()))


@pytest.mark.asyncio
async def test_generate_sanitizes_provider_status_errors() -> None:
    request = httpx2.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx2.Response(
        401,
        request=request,
        headers={"x-request-id": "req-safe-id"},
        json={"error": {"message": "super-secret-provider-body"}},
    )
    gateway, _ = _gateway(
        APIStatusError(
            "super-secret-provider-body",
            response=response,
            body={"error": {"message": "super-secret-provider-body"}},
        )
    )

    with pytest.raises(ModelProviderError) as exc_info:
        await gateway.generate(ModelRequest(messages=()))

    message = str(exc_info.value)
    assert "status=401" in message
    assert "request_id=req-safe-id" in message
    assert "super-secret-provider-body" not in message


@pytest.mark.asyncio
async def test_stream_emits_text_and_merges_interleaved_tool_fragments_by_index() -> None:
    chunks = [
        _chunk(text="先"),
        _chunk(
            tool_calls=[
                _namespace(
                    index=0,
                    id="call-a",
                    function=_namespace(name="sea", arguments='{"q"'),
                ),
                _namespace(
                    index=1,
                    id="call-b",
                    function=_namespace(name="look", arguments='{"id"'),
                ),
            ]
        ),
        _chunk(
            text="查",
            tool_calls=[
                _namespace(
                    index=1,
                    id=None,
                    function=_namespace(name="up", arguments=":2}"),
                ),
                _namespace(
                    index=0,
                    id=None,
                    function=_namespace(name="rch", arguments=':"x"}'),
                ),
            ],
            finish_reason="tool_calls",
            usage=_namespace(prompt_tokens=4, completion_tokens=3, total_tokens=7),
        ),
    ]
    gateway, client = _gateway(chunks)

    events = [event async for event in gateway.stream(ModelRequest(messages=()))]

    assert [event.text_delta for event in events[:-1]] == ["先", "查"]
    response = events[-1].response
    assert response is not None
    assert response.text == "先查"
    assert response.tool_calls == (
        ToolCall("call-a", "search", {"q": "x"}),
        ToolCall("call-b", "lookup", {"id": 2}),
    )
    assert response.finish_reason == "tool_calls"
    assert response.usage == {
        "input_tokens": 4,
        "output_tokens": 3,
        "total_tokens": 7,
    }
    assert client.completions.calls[0]["stream"] is True
    assert "stream_options" not in client.completions.calls[0]


@pytest.mark.asyncio
async def test_stream_tolerates_missing_usage() -> None:
    gateway, _ = _gateway([_chunk(text="ok", finish_reason="stop")])

    events = [event async for event in gateway.stream(ModelRequest(messages=()))]

    assert events[-1].response is not None
    assert events[-1].response.usage == {}


@pytest.mark.asyncio
async def test_stream_rejects_missing_tool_name() -> None:
    gateway, _ = _gateway(
        [
            _chunk(
                tool_calls=[
                    _namespace(
                        index=0,
                        id="call-a",
                        function=_namespace(name=None, arguments='{"q":"x"}'),
                    )
                ]
            )
        ]
    )

    with pytest.raises(ValueError, match="tool call without a function name"):
        _ = [event async for event in gateway.stream(ModelRequest(messages=()))]


@pytest.mark.asyncio
async def test_stream_sanitizes_provider_errors_before_iteration() -> None:
    request = httpx2.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx2.Response(
        429,
        request=request,
        headers={"x-request-id": "req-rate-limit"},
        json={"error": {"message": "sensitive-rate-limit-body"}},
    )
    gateway, _ = _gateway(
        APIStatusError(
            "sensitive-rate-limit-body",
            response=response,
            body={"error": {"message": "sensitive-rate-limit-body"}},
        )
    )

    with pytest.raises(ModelProviderError) as exc_info:
        _ = [event async for event in gateway.stream(ModelRequest(messages=()))]

    assert str(exc_info.value) == (
        "Model provider request failed (status=429, request_id=req-rate-limit)"
    )


@pytest.mark.asyncio
async def test_stream_sanitizes_provider_errors_during_iteration() -> None:
    request = httpx2.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx2.Response(
        502,
        request=request,
        json={"error": {"message": "sensitive-upstream-body"}},
    )
    gateway, _ = _gateway(
        [
            _chunk(text="partial"),
            APIStatusError(
                "sensitive-upstream-body",
                response=response,
                body={"error": {"message": "sensitive-upstream-body"}},
            ),
        ]
    )

    with pytest.raises(ModelProviderError) as exc_info:
        _ = [event async for event in gateway.stream(ModelRequest(messages=()))]

    assert str(exc_info.value) == "Model provider request failed (status=502)"


@pytest.mark.asyncio
async def test_stream_rejects_empty_provider_stream() -> None:
    gateway, _ = _gateway([])

    with pytest.raises(RuntimeError, match="empty stream"):
        _ = [event async for event in gateway.stream(ModelRequest(messages=()))]
