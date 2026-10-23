"""Strict payload contracts for the small MVP capability surface."""

from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FeishuDocumentPayload(_StrictPayload):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)
    parent_token: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")


class FeishuCalendarPayload(_StrictPayload):
    summary: str = Field(min_length=1, max_length=500)
    start: datetime
    end: datetime
    calendar_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "FeishuCalendarPayload":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class WpsDocumentPayload(_StrictPayload):
    name: str = Field(min_length=1, max_length=255)
    file_type: Literal["docx"] = "docx"


class NeteaseSearchPayload(_StrictPayload):
    since: date = Field(default_factory=lambda: date.today() - timedelta(days=30))
    limit: Annotated[int, Field(ge=1, le=100)] = 20

    @model_validator(mode="after")
    def enforce_recent_window(self) -> "NeteaseSearchPayload":
        today = date.today()
        if self.since > today or self.since < today - timedelta(days=90):
            raise ValueError("since must be within the last 90 days")
        return self


PAYLOAD_MODELS: dict[str, type[_StrictPayload]] = {
    "feishu:document.create": FeishuDocumentPayload,
    "feishu:calendar.create": FeishuCalendarPayload,
    "wps:document.create": WpsDocumentPayload,
    "netease_mail:email.search_recruiting": NeteaseSearchPayload,
}


def validate_capability_payload(
    provider_id: str, capability: str, payload: dict[str, Any]
) -> dict[str, Any]:
    model = PAYLOAD_MODELS[f"{provider_id}:{capability}"]
    return model.model_validate(payload).model_dump(mode="json", exclude_none=True)
