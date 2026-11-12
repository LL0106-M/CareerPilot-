from typing import Any, Protocol

from openai import APIError, OpenAI

from careerpilot.config import Settings
from careerpilot.harness.errors import sanitize_provider_error


class EmbeddingProvider(Protocol):
    """Minimal provider contract so dense retrieval is optional and replaceable."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingsClient(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        client: EmbeddingsClient,
        *,
        model: str,
        query_instruction: str,
        batch_size: int = 128,
    ) -> None:
        self._client = client
        self._model = model
        self._query_instruction = query_instruction.strip()
        self._batch_size = max(1, batch_size)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = self._create(batch)
            vectors.extend(_ordered_vectors(response, len(batch)))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        query = (
            f"Instruct: {self._query_instruction}\nQuery: {text}"
            if self._query_instruction
            else text
        )
        response = self._create([query])
        return _ordered_vectors(response, 1)[0]

    def _create(self, values: list[str]) -> Any:
        try:
            return self._client.create(
                model=self._model,
                input=values,
                encoding_format="float",
            )
        except APIError as exc:
            raise sanitize_provider_error(exc) from None


def _ordered_vectors(response: Any, expected_count: int) -> list[list[float]]:
    data = list(getattr(response, "data", ()))
    indexed: dict[int, list[float]] = {}
    for item in data:
        index = getattr(item, "index", None)
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError("Embedding response is missing index")
        if index in indexed:
            raise ValueError("Embedding response contains duplicate index")
        if index < 0 or index >= expected_count:
            raise ValueError("Embedding response index is out of range")
        embedding = getattr(item, "embedding", None)
        if not isinstance(embedding, list):
            raise ValueError("Embedding response is missing a vector")
        indexed[index] = [float(value) for value in embedding]
    if len(indexed) != expected_count:
        raise ValueError("Embedding response count mismatch")
    return [indexed[index] for index in range(expected_count)]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """Create optional dense embeddings; sparse retrieval remains available without it."""

    if not settings.embedding_model:
        return None
    api_key = settings.embedding_api_key or settings.model_api_key
    client = OpenAI(
        api_key=api_key.get_secret_value(),
        base_url=settings.embedding_base_url or settings.model_base_url,
        max_retries=1,
    )
    return OpenAICompatibleEmbeddingProvider(
        client.embeddings,
        model=settings.embedding_model,
        query_instruction=settings.embedding_query_instruction,
    )
