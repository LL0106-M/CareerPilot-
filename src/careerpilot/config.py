from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
        default="qwen3.7-plus-2026-05-26",
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
    dashscope_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="DASHSCOPE_API_KEY",
    )
    dashscope_base_url: str | None = Field(
        default=None,
        validation_alias="CAREERPILOT_DASHSCOPE_BASE_URL",
    )
    search_model: str = Field(
        default="qwen3.7-plus-2026-05-26",
        validation_alias="CAREERPILOT_SEARCH_MODEL",
    )
    search_default_strategy: Literal["turbo", "max"] = Field(
        default="turbo",
        validation_alias="CAREERPILOT_SEARCH_DEFAULT_STRATEGY",
    )
    search_escalation_strategy: Literal["turbo", "max"] = Field(
        default="max",
        validation_alias="CAREERPILOT_SEARCH_ESCALATION_STRATEGY",
    )
    search_timeout_seconds: float = Field(
        default=45.0,
        gt=0,
        validation_alias="CAREERPILOT_SEARCH_TIMEOUT_SECONDS",
    )

    @field_validator("dashscope_base_url")
    @classmethod
    def normalize_dashscope_base_url(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else None

    @property
    def search_configured(self) -> bool:
        return self.dashscope_api_key is not None and self.dashscope_base_url is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
