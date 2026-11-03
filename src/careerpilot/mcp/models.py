from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

McpTransport = Literal["stdio", "streamable_http"]


class McpServerConfig(BaseModel):
    """Validated connection and policy settings for one MCP server."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str = ""
    transport: McpTransport
    enabled: bool = True
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    allowed_tools: frozenset[str] | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    descriptor_ttl_seconds: float = Field(default=300.0, ge=1, le=3600)
    max_result_chars: int = Field(default=12_000, ge=256, le=100_000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
        if not normalized:
            raise ValueError("server name must contain a letter or number")
        return normalized

    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_transport_fields(self) -> McpServerConfig:
        if self.transport == "stdio":
            if self.command is None:
                raise ValueError("stdio transport requires command")
            if self.url is not None:
                raise ValueError("stdio transport does not accept url")
            return self

        if self.url is None:
            raise ValueError("streamable_http transport requires url")
        if self.command is not None or self.args or self.env:
            raise ValueError("streamable_http transport does not accept command, args, or env")
        parsed = urlsplit(self.url)
        if parsed.username or parsed.password:
            raise ValueError("MCP URL must not contain credentials")
        loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
            raise ValueError("remote MCP URL must use HTTPS; HTTP is allowed only on loopback")
        if not parsed.netloc:
            raise ValueError("MCP URL must include a host")
        return self

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"descriptor_ttl_seconds"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class McpToolDescriptor:
    server_name: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    title: str | None = None
    read_only: bool | None = None
    destructive: bool | None = None
    server_description: str = ""
    server_fingerprint: str = ""

    @property
    def namespaced_name(self) -> str:
        return f"mcp__{self.server_name}__{self.tool_name}"


@dataclass(frozen=True, slots=True)
class McpToolResult:
    status: Literal["completed", "failed", "forbidden"]
    server_name: str
    tool_name: str
    structured_content: dict[str, Any] | None = None
    text_content: tuple[str, ...] = ()
    error: str | None = None
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
