from careerpilot.config import Settings
from careerpilot.rag.embeddings import InstructEmbeddingProvider, create_embedding_provider


def test_embedding_provider_is_disabled_without_model_configuration() -> None:
    settings = Settings(_env_file=None)

    assert create_embedding_provider(settings) is None


class _EmbeddingClient:
    def __init__(self) -> None:
        self.document_batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_batches.append(texts)
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query = text
        return [1.0]


def test_query_instruction_is_applied_only_to_queries() -> None:
    client = _EmbeddingClient()
    provider = InstructEmbeddingProvider(client, query_instruction="Retrieve career evidence")

    provider.embed_documents(["document"])
    provider.embed_query("产品经理岗位")

    assert client.query == "Instruct: Retrieve career evidence\nQuery: 产品经理岗位"


def test_document_embeddings_are_batched_for_offline_indexing() -> None:
    client = _EmbeddingClient()
    provider = InstructEmbeddingProvider(
        client,
        query_instruction="Retrieve career evidence",
        batch_size=2,
    )

    vectors = provider.embed_documents(["一", "二二", "三三三"])

    assert vectors == [[1.0], [2.0], [3.0]]
    assert client.document_batches == [["一", "二二"], ["三三三"]]
