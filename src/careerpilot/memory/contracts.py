from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from careerpilot.memory.models import MemoryConfidence, MemorySensitivity, MemoryType

MAX_CLAIM_CONTENT_LENGTH = 1_000
MAX_EVIDENCE_EXCERPT_LENGTH = 500


class MemoryCognitiveClass(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PROSPECTIVE = "prospective"


class MemorySubject(StrEnum):
    SELF = "self"
    PEER = "peer"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class MemoryAuthorship(StrEnum):
    USER_EXPLICIT = "user_explicit"
    USER_CONFIRMED = "user_confirmed"
    AGENT_INFERRED = "agent_inferred"
    SYSTEM_OBSERVED = "system_observed"
    IMPORTED = "imported"


class MemoryDurability(StrEnum):
    TRANSIENT = "transient"
    EPISODIC = "episodic"
    DURABLE = "durable"


class AdmissionDecision(StrEnum):
    COMMIT = "commit"
    PENDING = "pending"
    IGNORE = "ignore"
    REJECT = "reject"


class PatchOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    SUPERSEDE = "supersede"
    DELETE = "delete"
    NOOP = "noop"


class AdmissionReason(StrEnum):
    DURABLE_USER_EXPLICIT = "durable_user_explicit"
    USER_CONFIRMED = "user_confirmed"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    SENSITIVE_REQUIRES_CONFIRMATION = "sensitive_requires_confirmation"
    INFERRED_REQUIRES_CONFIRMATION = "inferred_requires_confirmation"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICT_REQUIRES_CONFIRMATION = "conflict_requires_confirmation"
    TRANSIENT_CONTENT = "transient_content"
    NON_SELF_SUBJECT = "non_self_subject"
    IRRELEVANT_CONTENT = "irrelevant_content"
    PROMPT_INJECTION = "prompt_injection"
    CREDENTIAL_MATERIAL = "credential_material"
    CROSS_OWNER_CLAIM = "cross_owner_claim"
    INVALID_EVIDENCE = "invalid_evidence"
    PROHIBITED_INFERENCE = "prohibited_inference"


def _normalized_text(value: str, *, field_name: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(normalized) > limit:
        raise ValueError(f"{field_name} exceeds {limit} characters")
    return normalized


@dataclass(frozen=True, slots=True)
class MemoryEvidenceRef:
    message_id: str
    excerpt: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "message_id",
            _normalized_text(self.message_id, field_name="message_id", limit=200),
        )
        excerpt = " ".join(self.excerpt.split())
        if not excerpt:
            raise ValueError("evidence excerpt must not be empty")
        object.__setattr__(self, "excerpt", excerpt[:MAX_EVIDENCE_EXCERPT_LENGTH])


@dataclass(frozen=True, slots=True)
class MemoryClaim:
    content: str
    memory_type: MemoryType
    cognitive_class: MemoryCognitiveClass
    subject: MemorySubject
    authorship: MemoryAuthorship
    evidence: tuple[MemoryEvidenceRef, ...]
    durability: MemoryDurability
    sensitivity: MemorySensitivity
    confidence: MemoryConfidence
    correction_hint: str | None = None
    target_memory_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "content",
            _normalized_text(
                self.content,
                field_name="content",
                limit=MAX_CLAIM_CONTENT_LENGTH,
            ),
        )
        if not self.evidence:
            raise ValueError("evidence must contain at least one source excerpt")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if self.correction_hint is not None:
            object.__setattr__(
                self,
                "correction_hint",
                _normalized_text(
                    self.correction_hint,
                    field_name="correction_hint",
                    limit=300,
                ),
            )
        if self.target_memory_id is not None:
            object.__setattr__(
                self,
                "target_memory_id",
                _normalized_text(
                    self.target_memory_id,
                    field_name="target_memory_id",
                    limit=200,
                ),
            )


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    decision: AdmissionDecision
    reason_code: str
    claim: MemoryClaim

    def __post_init__(self) -> None:
        reason_code = self.reason_code.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", reason_code):
            raise ValueError("reason_code must be a stable snake_case identifier")
        object.__setattr__(self, "reason_code", reason_code)


@dataclass(frozen=True, slots=True)
class MemoryPatch:
    operation: PatchOperation
    claim: MemoryClaim
    admission: AdmissionResult
    target_memory_id: str | None = None

    def __post_init__(self) -> None:
        if self.admission.claim != self.claim:
            raise ValueError("admission claim must match patch claim")
        if self.operation in {
            PatchOperation.UPDATE,
            PatchOperation.SUPERSEDE,
            PatchOperation.DELETE,
        } and not self.target_memory_id:
            raise ValueError("target_memory_id is required for existing-memory patches")
        if self.target_memory_id is not None:
            object.__setattr__(
                self,
                "target_memory_id",
                _normalized_text(
                    self.target_memory_id,
                    field_name="target_memory_id",
                    limit=200,
                ),
            )
