from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from openai import APIStatusError

from careerpilot.config import Settings
from careerpilot.harness.errors import ModelProviderError
from careerpilot.rag.embeddings import (
    OpenAICompatibleEmbeddingProvider,
    create_embedding_provider,
)


class FakeEmbeddings:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        rows = self.responses.pop(0)
        if isinstance(rows, BaseException):
            raise rows
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=embedding)
                for index, embedding in rows
            ]
        )


def test_embedding_provider_is_disabled_without_model_configuration() -> None:
    settings = Settings(_env_file=None)

    assert create_embedding_provider(settings) is None


def test_documents_are_batched_and_response_order_is_restored() -> None:
    client = FakeEmbeddings(
        [
            [(1, [2.5, 2.0]), (0, [1.5, 1.0])],
            [(0, [3.5, 3.0])],
        ]
    )
    provider = OpenAICompatibleEmbeddingProvider(
        client,
        model="embed-model",
        query_instruction="Retrieve career evidence",
        batch_size=2,
    )

    vectors = provider.embed_documents(["一", "二二", "三三三"])

    assert vectors == [[1.5, 1.0], [2.5, 2.0], [3.5, 3.0]]
    assert [call["input"] for call in client.calls] == [
        ["一", "二二"],
        ["三三三"],
    ]
    assert all(call["model"] == "embed-model" for call in client.calls)
    assert all(call["encoding_format"] == "float" for call in client.calls)


def test_query_instruction_is_applied_only_to_queries() -> None:
    client = FakeEmbeddings([[(0, [1.25, 2.5])], [(0, [3.0])]])
    provider = OpenAICompatibleEmbeddingProvider(
        client,
        model="embed-model",
        query_instruction="Retrieve career evidence",
    )

    query_vector = provider.embed_query("产品经理岗位")
    provider.embed_documents(["document"])

    assert query_vector == [1.25, 2.5]
    assert client.calls[0]["input"] == [
        "Instruct: Retrieve career evidence\nQuery: 产品经理岗位"
    ]
    assert client.calls[1]["input"] == ["document"]


def test_empty_document_list_does_not_call_provider() -> None:
    client = FakeEmbeddings([])
    provider = OpenAICompatibleEmbeddingProvider(
        client, model="embed-model", query_instruction=""
    )

    assert provider.embed_documents([]) == []
    assert client.calls == []


@pytest.mark.parametrize(
    "rows, message",
    [
        ([(None, [1.0])], "missing index"),
        ([(0, [1.0])], "count mismatch"),
        ([(0, [1.0]), (0, [2.0])], "duplicate index"),
    ],
)
def test_invalid_embedding_response_is_rejected(rows, message: str) -> None:
    client = FakeEmbeddings([rows])
    provider = OpenAICompatibleEmbeddingProvider(
        client, model="embed-model", query_instruction=""
    )

    with pytest.raises(ValueError, match=message):
        provider.embed_documents(["a", "b"])


@pytest.mark.parametrize("method", ["documents", "query"])
def test_embedding_provider_sanitizes_provider_error(method: str) -> None:
    request = httpx2.Request("POST", "https://provider.example/v1/embeddings")
    response = httpx2.Response(
        500,
        request=request,
        headers={"x-request-id": "req-embedding"},
        json={"error": {"message": "sensitive-embedding-body"}},
    )
    client = FakeEmbeddings(
        [
            APIStatusError(
                "sensitive-embedding-body",
                response=response,
                body={"error": {"message": "sensitive-embedding-body"}},
            )
        ]
    )
    provider = OpenAICompatibleEmbeddingProvider(
        client, model="embed-model", query_instruction=""
    )

    with pytest.raises(ModelProviderError) as exc_info:
        if method == "documents":
            provider.embed_documents(["document"])
        else:
            provider.embed_query("query")

    message = str(exc_info.value)
    assert "status=500" in message
    assert "request_id=req-embedding" in message
    assert "sensitive-embedding-body" not in message
