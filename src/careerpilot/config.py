from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables only."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.embedding"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "careerpilot-agent"
    environment: Literal["development", "test", "production"] = Field(
        default="development",
        validation_alias="CAREERPILOT_ENVIRONMENT",
    )
    cookie_secret: SecretStr = Field(
        default=SecretStr("careerpilot-development-cookie-secret-change-me"),
        validation_alias="CAREERPILOT_COOKIE_SECRET",
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CAREERPILOT_CORS_ORIGINS",
    )
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
    embedding_query_instruction: str = Field(
        default=(
            "Retrieve relevant career knowledge, job information, and interview "
            "preparation evidence for the user query."
        ),
        validation_alias="CAREERPILOT_EMBEDDING_QUERY_INSTRUCTION",
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
    memory_db_path: Path = Field(
        default=Path("data/memory/careerpilot.db"),
        validation_alias="CAREERPILOT_MEMORY_DB_PATH",
    )
    product_db_path: Path = Field(
        default=Path("data/product/careerpilot.db"),
        validation_alias="CAREERPILOT_PRODUCT_DB_PATH",
    )
    action_db_path: Path = Field(
        default=Path("data/actions/careerpilot.db"),
        validation_alias="CAREERPILOT_ACTION_DB_PATH",
    )
    feishu_cli_executable: str = Field(
        default="lark-cli",
        validation_alias="CAREERPILOT_FEISHU_CLI_EXECUTABLE",
    )
    feishu_cli_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        validation_alias="CAREERPILOT_FEISHU_CLI_TIMEOUT_SECONDS",
    )
    wps_base_url: str = Field(
        default="https://openapi.wps.cn",
        validation_alias="CAREERPILOT_WPS_BASE_URL",
    )
    wps_access_token: SecretStr | None = Field(
        default=None,
        validation_alias="CAREERPILOT_WPS_ACCESS_TOKEN",
    )
    wps_access_key: SecretStr | None = Field(
        default=None,
        validation_alias="CAREERPILOT_WPS_ACCESS_KEY",
    )
    wps_secret_key: SecretStr | None = Field(
        default=None,
        validation_alias="CAREERPILOT_WPS_SECRET_KEY",
    )
    wps_drive_id: str | None = Field(default=None, validation_alias="CAREERPILOT_WPS_DRIVE_ID")
    wps_parent_id: str | None = Field(
        default=None,
        validation_alias="CAREERPILOT_WPS_PARENT_ID",
    )
    netease_imap_host: str = Field(
        default="imap.163.com",
        validation_alias="CAREERPILOT_NETEASE_IMAP_HOST",
    )
    netease_imap_port: int = Field(
        default=993,
        ge=1,
        le=65535,
        validation_alias="CAREERPILOT_NETEASE_IMAP_PORT",
    )
    netease_account: str | None = Field(
        default=None,
        validation_alias="CAREERPILOT_NETEASE_ACCOUNT",
    )
    netease_authorization_code: SecretStr | None = Field(
        default=None,
        validation_alias="CAREERPILOT_NETEASE_AUTHORIZATION_CODE",
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

    @model_validator(mode="after")
    def validate_wps_signing_pair(self) -> "Settings":
        if (self.wps_access_key is None) != (self.wps_secret_key is None):
            raise ValueError("WPS access key and secret key must be configured together")
        return self

    @property
    def search_configured(self) -> bool:
        return self.dashscope_api_key is not None and self.dashscope_base_url is not None

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
