import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from careerpilot.memory.base import MemoryContext


class DreamingTrigger(StrEnum):
    MANUAL_REVIEW = "manual_review"
    CAREER_MILESTONE = "career_milestone"


class DreamingTriggerPolicy:
    """Trigger consolidation only for explicit reflection or meaningful career events."""

    _review_markers = ("复盘", "回顾一下", "总结我的职业", "阶段总结", "整理这段经历")
    _milestone_markers = (
        "拿到offer",
        "拿到 offer",
        "收到offer",
        "收到 offer",
        "面试结束",
        "面试完",
        "被拒",
        "拒信",
        "入职",
        "离职",
        "转岗",
    )

    def detect(self, message: str) -> DreamingTrigger | None:
        normalized = message.strip().lower()
        if any(marker in normalized for marker in self._review_markers):
            return DreamingTrigger.MANUAL_REVIEW
        if any(marker in normalized for marker in self._milestone_markers):
            return DreamingTrigger.CAREER_MILESTONE
        return None


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    id: str
    content: str
    source: str


@dataclass(frozen=True, slots=True)
class DreamingSnapshot:
    user_id: str
    conversation_id: str
    trigger: DreamingTrigger
    user_message: str
    assistant_message: str
    evidence: tuple[EvidenceRef, ...]

    @classmethod
    def from_turn(
        cls,
        *,
        user_id: str,
        conversation_id: str,
        trigger: DreamingTrigger,
        user_message: str,
        assistant_message: str,
        memories: MemoryContext,
    ) -> "DreamingSnapshot":
        evidence = [
            EvidenceRef(
                id=(
                    f"turn:{conversation_id}:"
                    f"{hashlib.sha256(user_message.encode('utf-8')).hexdigest()[:16]}"
                ),
                content=user_message,
                source="current_turn",
            )
        ]
        evidence.extend(
            EvidenceRef(item.id, item.content, "memory")
            for item in (*memories.facts, *memories.preferences)
            if item.id
        )
        return cls(
            user_id=user_id,
            conversation_id=conversation_id,
            trigger=trigger,
            user_message=user_message,
            assistant_message=assistant_message,
            evidence=tuple(evidence),
        )


@dataclass(frozen=True, slots=True)
class HypothesisProposal:
    statement: str
    confidence_band: str
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CareerHypothesis:
    id: str
    user_id: str
    statement: str
    status: str
    confidence_band: str
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    open_questions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DreamingJob:
    id: str
    snapshot: DreamingSnapshot
    attempts: int


class DreamingAnalyzer(Protocol):
    async def analyze(self, snapshot: DreamingSnapshot) -> tuple[HypothesisProposal, ...]: ...


class CognitiveStore(Protocol):
    def enqueue(self, snapshot: DreamingSnapshot) -> bool: ...

    def claim_next(self) -> DreamingJob | None: ...

    def complete(self, job: DreamingJob, proposals: tuple[HypothesisProposal, ...]) -> None: ...

    def fail(self, job: DreamingJob, error: str) -> None: ...

    def list_hypotheses(self, user_id: str, limit: int = 5) -> tuple[CareerHypothesis, ...]: ...


class DreamingProcessor:
    def __init__(self, store: CognitiveStore, analyzer: DreamingAnalyzer) -> None:
        self._store = store
        self._analyzer = analyzer

    async def run_once(self) -> bool:
        job = self._store.claim_next()
        if job is None:
            return False
        try:
            proposals = await self._analyzer.analyze(job.snapshot)
            self._store.complete(job, proposals)
        except Exception as exc:
            self._store.fail(job, type(exc).__name__)
            raise
        return True
