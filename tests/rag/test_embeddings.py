from careerpilot.config import Settings
from careerpilot.rag.embeddings import create_embedding_provider


def test_embedding_provider_is_disabled_without_model_configuration() -> None:
    settings = Settings(_env_file=None)

    assert create_embedding_provider(settings) is None
