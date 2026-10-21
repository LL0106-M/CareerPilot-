from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "careerpilot-agent"
    model_base_url: str = Field(
        default="http://127.0.0.1:8000/v1",
        validation_alias="CAREERPILOT_MODEL_BASE_URL",
    )
    model_api_key: SecretStr = Field(
        default=SecretStr("local-development"),
        validation_alias="CAREERPILOT_MODEL_API_KEY",
    )
    model_name: str = Field(
        default="Qwen/Qwen3.8-27B",
        validation_alias="CAREERPILOT_MODEL_NAME",
    )
    exploration_temperature: float = Field(
        default=0.4,
        validation_alias="CAREERPILOT_EXPLORATION_TEMPERATURE",
    )
    reasoning_temperature: float = Field(
        default=0.0,
        validation_alias="CAREERPILOT_REASONING_TEMPERATURE",
    )
    embedding_model: str | None = Field(
        default=None,
        validation_alias="CAREERPILOT_EMBEDDING_MODEL",
    )
    embedding_base_url: str | None = Field(
        default=None,
        validation_alias="CAREERPILOT_EMBEDDING_BASE_URL",
    )
    embedding_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="CAREERPILOT_EMBEDDING_API_KEY",
    )
    memos_api_key: SecretStr | None = Field(default=None, validation_alias="MEMOS_API_KEY")
    memos_base_url: str = Field(
        default="https://memos.memtensor.cn/api/openmem/v1",
        validation_alias="MEMOS_BASE_URL",
    )
    rag_db_path: Path = Field(
        default=Path("data/rag/careerpilot.db"),
        validation_alias="CAREERPILOT_RAG_DB_PATH",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
