from dataclasses import dataclass
from enum import StrEnum


class SearchStrategy(StrEnum):
    TURBO = "turbo"
    MAX = "max"


@dataclass(frozen=True, slots=True)
class WebSearchSource:
    url: str
    title: str
    site_name: str | None = None
    index: int | None = None


@dataclass(frozen=True, slots=True)
class WebSearchResponse:
    answer: str
    sources: tuple[WebSearchSource, ...]
    strategy: SearchStrategy
    request_id: str | None = None
    partial: bool = False

