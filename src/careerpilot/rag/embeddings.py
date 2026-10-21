from typing import Protocol

from langchain_openai import OpenAIEmbeddings

from careerpilot.config import Settings


class EmbeddingProvider(Protocol):
    """Minimal provider contract so dense retrieval is optional and replaceable."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def create_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """Create optional dense embeddings; sparse retrieval remains available without it."""

    if not settings.embedding_model:
        return None
    api_key = settings.embedding_api_key or settings.model_api_key
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.embedding_base_url or settings.model_base_url,
        api_key=api_key.get_secret_value(),
        check_embedding_ctx_length=False,
    )
