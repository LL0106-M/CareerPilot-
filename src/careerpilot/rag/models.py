from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class KnowledgeOrigin(StrEnum):
    SYSTEM_CURATED = "system_curated"
    SYSTEM_WEB = "system_web"
    USER_PROVIDED = "user_provided"


@dataclass(frozen=True, slots=True)
class SourceDocument:
    id: str
    title: str
    source_uri: str
    source_type: str
    domain: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    published_at: str | None = None
    fetched_at: str | None = None
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED
    owner_user_id: str | None = None

    def __post_init__(self) -> None:
        if self.knowledge_origin is KnowledgeOrigin.USER_PROVIDED and not self.owner_user_id:
            raise ValueError("user-provided documents require owner_user_id")
        if self.knowledge_origin is not KnowledgeOrigin.USER_PROVIDED and self.owner_user_id:
            raise ValueError("only user-provided documents may have owner_user_id")


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    id: str
    document_id: str
    ordinal: int
    title: str
    heading: str
    content: str
    source_uri: str
    source_type: str
    domain: str
    metadata: dict[str, Any] = field(default_factory=dict)
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED
    owner_user_id: str | None = None


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: str
    document_id: str
    title: str
    heading: str
    content: str
    source_uri: str
    source_type: str
    domain: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_id: str | None = None
    evidence_kind: "EvidenceKind | None" = None
    parent_id: str | None = None
    channels: tuple[str, ...] = ()
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED
    owner_user_id: str | None = None


class EvidenceKind(StrEnum):
    PASSAGE = "passage"
    KG_TRIPLE = "kg_triple"
    TABLE_FACT = "table_fact"
    TABLE_ROW = "table_row"
    API_OBJECT = "api_object"


@dataclass(frozen=True, slots=True)
class KnowledgeTriple:
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True, slots=True)
class EvidenceUnit:
    id: str
    kind: EvidenceKind
    document_id: str
    parent_id: str | None
    title: str
    embedding_text: str
    source_uri: str
    source_type: str
    domain: str
    metadata: dict[str, Any] = field(default_factory=dict)
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED
    owner_user_id: str | None = None


@dataclass(frozen=True, slots=True)
class WebSource:
    url: str
    source_type: str
    domain: str
    crawl_interval_hours: int
    status: str = "active"
    last_crawled_at: str | None = None
    content_hash: str | None = None
