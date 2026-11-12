import re

from openai import APIError, APIStatusError

_MAX_REQUEST_ID_LENGTH = 128
_UNSAFE_REQUEST_ID_CHARACTER = re.compile(r"[^A-Za-z0-9._:-]")


class ModelProviderError(RuntimeError):
    """Safe public error raised when an official SDK provider request fails."""


def sanitize_provider_error(exc: APIError) -> ModelProviderError:
    """Convert an SDK exception without exposing response bodies or provider text."""

    details: list[str] = []
    if isinstance(exc, APIStatusError):
        details.append(f"status={exc.status_code}")
        request_id = _safe_request_id(exc.request_id)
        if request_id:
            details.append(f"request_id={request_id}")
    suffix = f" ({', '.join(details)})" if details else ""
    return ModelProviderError(f"Model provider request failed{suffix}")


def _safe_request_id(value: object) -> str:
    if not isinstance(value, str):
        return ""
    shortened = value[:_MAX_REQUEST_ID_LENGTH]
    return _UNSAFE_REQUEST_ID_CHARACTER.sub("?", shortened)
