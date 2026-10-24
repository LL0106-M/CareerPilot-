from typing import Protocol

from langchain_openai import OpenAIEmbeddings

from careerpilot.config import Settings


class EmbeddingProvider(Protocol):
    """Minimal provider contract so dense retrieval is optional and replaceable."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class InstructEmbeddingProvider:
    def __init__(
        self,
        client: OpenAIEmbeddings,
        *,
        query_instruction: str,
        batch_size: int = 128,
    ) -> None:
        self._client = client
        self._query_instruction = query_instruction.strip()
        self._batch_size = max(1, batch_size)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            vectors.extend(self._client.embed_documents(texts[start : start + self._batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        query = (
            f"Instruct: {self._query_instruction}\nQuery: {text}"
            if self._query_instruction
            else text
        )
        return self._client.embed_query(query)


def create_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """Create optional dense embeddings; sparse retrieval remains available without it."""

    if not settings.embedding_model:
        return None
    api_key = settings.embedding_api_key or settings.model_api_key
    client = OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.embedding_base_url or settings.model_base_url,
        api_key=api_key.get_secret_value(),
        check_embedding_ctx_length=False,
        model_kwargs={"encoding_format": "float"},
    )
    return InstructEmbeddingProvider(
        client,
        query_instruction=settings.embedding_query_instruction,
    )
