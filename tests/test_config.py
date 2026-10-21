from pathlib import Path

import pytest
from pydantic import ValidationError

from careerpilot.config import Settings


def test_settings_reads_rag_database_path(monkeypatch) -> None:
    monkeypatch.setenv("CAREERPILOT_RAG_DB_PATH", "var/index/career.db")

    settings = Settings(_env_file=None)

    assert settings.rag_db_path == Path("var/index/career.db")


def test_settings_reads_cognitive_memory_database_path(monkeypatch) -> None:
    monkeypatch.setenv("CAREERPILOT_MEMORY_DB_PATH", "var/memory/career.db")

    settings = Settings(_env_file=None)

    assert settings.memory_db_path == Path("var/memory/career.db")


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


def test_production_defaults_pin_qwen_37_plus_snapshot() -> None:
    settings = Settings(_env_file=None)

    assert settings.model_name == "qwen3.7-plus-2026-05-26"
    assert settings.search_model == "qwen3.7-plus-2026-05-26"
    assert settings.search_default_strategy == "turbo"
    assert settings.search_escalation_strategy == "max"


def test_dashscope_search_is_configured_only_with_key_and_base_url(monkeypatch) -> None:
    no_search = Settings(_env_file=None)
    assert no_search.search_configured is False

    monkeypatch.setenv("DASHSCOPE_API_KEY", "secret")
    monkeypatch.setenv(
        "CAREERPILOT_DASHSCOPE_BASE_URL",
        "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/",
    )
    configured = Settings(_env_file=None)

    assert configured.search_configured is True
    assert configured.dashscope_base_url == (
        "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1"
    )


def test_search_strategy_rejects_nested_agent_mode(monkeypatch) -> None:
    monkeypatch.setenv("CAREERPILOT_SEARCH_DEFAULT_STRATEGY", "agent")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
