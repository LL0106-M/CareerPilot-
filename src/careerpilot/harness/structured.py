from typing import Any, Protocol, TypeVar

from openai import APIError
from pydantic import BaseModel

from careerpilot.harness.errors import sanitize_provider_error

StructuredResult = TypeVar("StructuredResult", bound=BaseModel)
_TOOL_NAME = "emit_structured_result"


class StructuredGenerator(Protocol):
    def generate(
        self,
        prompt: str,
        response_model: type[StructuredResult],
    ) -> StructuredResult: ...


class StructuredCompletionsClient(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class StructuredChatClient(Protocol):
    completions: StructuredCompletionsClient


class StructuredClient(Protocol):
    chat: StructuredChatClient


class OpenAICompatibleStructuredGenerator:
    """Synchronous structured generation for offline ingestion pipelines."""

    def __init__(
        self,
        client: StructuredClient,
        *,
        model: str,
        temperature: float,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    def generate(
        self,
        prompt: str,
        response_model: type[StructuredResult],
    ) -> StructuredResult:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self._temperature,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": _TOOL_NAME,
                            "description": (
                                "Return the extracted data in the required schema."
                            ),
                            "parameters": response_model.model_json_schema(),
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            )
        except APIError as exc:
            raise sanitize_provider_error(exc) from None
        choices = getattr(completion, "choices", ())
        if not choices:
            raise RuntimeError("Model provider returned no choices")
        calls = getattr(choices[0].message, "tool_calls", None) or ()
        if len(calls) != 1:
            raise ValueError("Structured model response must contain exactly one tool call")
        function = getattr(calls[0], "function", None)
        if function is None or getattr(function, "name", None) != _TOOL_NAME:
            raise ValueError("Structured model response used an unexpected tool")
        arguments = getattr(function, "arguments", None)
        if not isinstance(arguments, str):
            raise ValueError("Structured model arguments must be JSON text")
        return response_model.model_validate_json(arguments)
