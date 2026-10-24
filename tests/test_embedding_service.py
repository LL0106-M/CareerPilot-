from fastapi.testclient import TestClient

from careerpilot.embedding_service import EmbeddingEngine, create_embedding_app


class _Vectors:
    def __init__(self, values: list[list[float]]) -> None:
        self._values = values

    def tolist(self) -> list[list[float]]:
        return self._values


class _Tokenizer:
    def __call__(self, texts: list[str], **_: object) -> dict[str, list[list[int]]]:
        return {"input_ids": [[1] * len(text) for text in texts]}


class _Model:
    tokenizer = _Tokenizer()

    def encode(self, texts: list[str], **_: object) -> _Vectors:
        return _Vectors([[float(index), 1.0] for index, _text in enumerate(texts)])


def test_openai_compatible_embedding_endpoint() -> None:
    engine = EmbeddingEngine("test-model", model_factory=lambda *_args, **_kwargs: _Model())

    with TestClient(create_embedding_app(engine)) as client:
        response = client.post(
            "/v1/embeddings",
            json={"model": "test-model", "input": ["职业规划", "RAG"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][1]["embedding"] == [1.0, 1.0]
    assert payload["usage"]["prompt_tokens"] == 7
