from pathlib import Path

from careerpilot.config import Settings


def test_settings_reads_rag_database_path(monkeypatch) -> None:
    monkeypatch.setenv("CAREERPILOT_RAG_DB_PATH", "var/index/career.db")

    settings = Settings(_env_file=None)

    assert settings.rag_db_path == Path("var/index/career.db")


def test_settings_separates_exploration_and_reasoning_temperatures() -> None:
    settings = Settings(_env_file=None)

    assert settings.exploration_temperature == 0.4
    assert settings.reasoning_temperature == 0.0


def test_dense_embeddings_are_optional_and_openai_compatible(monkeypatch) -> None:
    monkeypatch.setenv("CAREERPILOT_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    monkeypatch.setenv("CAREERPILOT_EMBEDDING_BASE_URL", "http://127.0.0.1:8001/v1")

    settings = Settings(_env_file=None)

    assert settings.embedding_model == "Qwen/Qwen3-Embedding-0.6B"
    assert settings.embedding_base_url == "http://127.0.0.1:8001/v1"
