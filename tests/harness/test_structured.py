import json
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from openai import APIStatusError
from pydantic import BaseModel

from careerpilot.harness.errors import ModelProviderError
from careerpilot.harness.structured import OpenAICompatibleStructuredGenerator


class Result(BaseModel):
    value: str


class FakeCompletions:
    def __init__(self, results: list[Any]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _completion(arguments: str, *, name: str = "emit_structured_result") -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(name=name, arguments=arguments)
                        )
                    ]
                )
            )
        ]
    )


def test_structured_generator_uses_tool_schema_and_validates_result() -> None:
    completions = FakeCompletions([_completion(json.dumps({"value": "ok"}))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    generator = OpenAICompatibleStructuredGenerator(
        client, model="test-model", temperature=0.0
    )

    result = generator.generate("extract", Result)

    assert result == Result(value="ok")
    call = completions.calls[0]
    assert call["tools"][0]["function"]["parameters"] == Result.model_json_schema()
    assert call["tool_choice"]["function"]["name"] == "emit_structured_result"


@pytest.mark.parametrize(
    "completion",
    [
        SimpleNamespace(choices=[]),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[]))]
        ),
        _completion("not-json"),
        _completion(json.dumps({"value": "ok"}), name="wrong"),
    ],
)
def test_structured_generator_rejects_malformed_provider_output(completion: Any) -> None:
    completions = FakeCompletions([completion])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    generator = OpenAICompatibleStructuredGenerator(
        client, model="test-model", temperature=0.0
    )

    with pytest.raises((RuntimeError, ValueError)):
        generator.generate("extract", Result)


def test_structured_generator_sanitizes_provider_error() -> None:
    request = httpx2.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx2.Response(
        403,
        request=request,
        headers={"x-request-id": "req-structured"},
        json={"error": {"message": "sensitive-structured-body"}},
    )
    completions = FakeCompletions(
        [
            APIStatusError(
                "sensitive-structured-body",
                response=response,
                body={"error": {"message": "sensitive-structured-body"}},
            )
        ]
    )
    generator = OpenAICompatibleStructuredGenerator(
        SimpleNamespace(chat=SimpleNamespace(completions=completions)),
        model="test-model",
        temperature=0.0,
    )

    with pytest.raises(ModelProviderError) as exc_info:
        generator.generate("extract", Result)

    message = str(exc_info.value)
    assert "status=403" in message
    assert "request_id=req-structured" in message
    assert "sensitive-structured-body" not in message
