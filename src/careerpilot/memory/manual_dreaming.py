from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from careerpilot.memory.cognitive_store import ManualDreamingJob, SqliteCognitiveStore
from careerpilot.memory.dreaming import (
    DreamingAnalysis,
    DreamingAnalyzer,
    DreamingSnapshot,
    DreamingTrigger,
    EvidenceRef,
)
from careerpilot.memory.models import (
    MemoryConfidence,
    MemoryOrigin,
    MemorySourceType,
    MemoryType,
)


class ManualDreamingNoEvidence(ValueError):
    pass


class MemoryReader(Protocol):
    def list(self, owner_id: str, **kwargs): ...
    def propose(self, **kwargs): ...


EvidenceCollector = Callable[[str, date], tuple[EvidenceRef, ...]]


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def collect_recent_evidence(owner_id, local_day, memories, product, rag) -> tuple[EvidenceRef, ...]:
    cutoff = datetime.combine(local_day - timedelta(days=6), time.min, tzinfo=UTC)
    evidence: list[EvidenceRef] = []
    for item in memories.list(owner_id, limit=200):
        updated = _as_datetime(getattr(item, "updated_at", None))
        if updated is not None and updated >= cutoff:
            kind = getattr(getattr(item, "type", None), "value", "memory")
            evidence.append(EvidenceRef(f"memory:{item.id}", item.content, kind))
    for conversation in product.list_conversations(owner_id):
        updated = _as_datetime(conversation.get("updated_at"))
        if updated is None or updated < cutoff:
            continue
        detail = product.get_conversation(owner_id, str(conversation["id"]))
        if detail is None:
            continue
        for index, message in enumerate(detail.get("messages", [])):
            if message.get("role") != "user" or not str(message.get("content", "")).strip():
                continue
            evidence.append(
                EvidenceRef(
                    f"conversation:{conversation['id']}:{index}",
                    str(message["content"]),
                    "conversation",
                )
            )
    for row in rag.list_user_documents(owner_id):
        uploaded = _as_datetime(row["uploaded_at"])
        if uploaded is not None and uploaded >= cutoff:
            evidence.append(EvidenceRef(f"document:{row['id']}", str(row["title"]), "knowledge"))
    return tuple(evidence)


class ManualDreamingService:
    def __init__(
        self,
        store: SqliteCognitiveStore,
        analyzer: DreamingAnalyzer,
        memories: MemoryReader,
        collector: EvidenceCollector,
    ) -> None:
        self._store = store
        self._analyzer = analyzer
        self._memories = memories
        self._collector = collector

    def start(self, owner_id: str, local_date: date) -> ManualDreamingJob:
        evidence = self._collector(owner_id, local_date)
        if not evidence:
            raise ManualDreamingNoEvidence("最近 7 天还没有足够内容，请先对话或记录一个想法。")
        payload = json.dumps(
            [{"id": item.id, "content": item.content, "source": item.source} for item in evidence],
            ensure_ascii=False,
        )
        return self._store.start_manual_job(owner_id, local_date.isoformat(), payload)

    async def run(self, owner_id: str, job_id: str) -> None:
        job = self._store.get_manual_job(owner_id, job_id)
        if job is None:
            raise ValueError("Manual Dreaming job not found")
        self._store.mark_manual_job_processing(owner_id, job_id)
        try:
            raw_evidence = json.loads(job.evidence_json)
            snapshot = DreamingSnapshot(
                user_id=owner_id,
                conversation_id=f"manual-dreaming:{job.local_date}",
                trigger=DreamingTrigger.MANUAL_REVIEW,
                user_message="请整理我最近 7 天的职业探索。",
                assistant_message="正在整理最近 7 天的线索。",
                evidence=tuple(EvidenceRef(**item) for item in raw_evidence),
            )
            analysis = await self._analyzer.analyze(snapshot)
            if not isinstance(analysis, DreamingAnalysis):
                analysis = DreamingAnalysis(hypotheses=tuple(analysis))
            self._store.complete_manual_job(owner_id, job_id, self._result_json(analysis))
        except Exception as error:
            self._store.fail_manual_job(owner_id, job_id, type(error).__name__)
            raise

    def status(self, owner_id: str, job_id: str) -> dict[str, object] | None:
        job = self._store.get_manual_job(owner_id, job_id)
        if job is None:
            return None
        result = self._store.get_manual_result(owner_id, job.local_date)
        return {
            "job_id": job.id,
            "status": job.status,
            "local_date": job.local_date,
            "error": job.last_error,
            "result": self._result_payload(result) if result is not None else None,
        }

    def today(self, owner_id: str, local_date: date) -> dict[str, object] | None:
        result = self._store.get_manual_result(owner_id, local_date.isoformat())
        if result is None:
            return None
        return self._result_payload(result)

    def confirm_hypothesis(self, owner_id: str, result_id: str, hypothesis_index: int) -> str:
        result = self._store.get_manual_result_by_id(owner_id, result_id)
        if result is None:
            raise ValueError("Dreaming result not found")
        payload = json.loads(result.result_json)
        hypotheses = payload.get("hypotheses", [])
        if hypothesis_index < 0 or hypothesis_index >= len(hypotheses):
            raise ValueError("Dreaming hypothesis not found")
        hypothesis = hypotheses[hypothesis_index]
        confidence = {
            "low": MemoryConfidence.LOW,
            "medium": MemoryConfidence.MEDIUM,
            "high": MemoryConfidence.HIGH,
        }.get(hypothesis.get("confidence_band"), MemoryConfidence.LOW)
        record = self._memories.propose(
            owner_id=owner_id,
            memory_type=MemoryType.HYPOTHESIS,
            content=str(hypothesis["statement"]),
            origin=MemoryOrigin.DREAMING,
            source_type=MemorySourceType.DREAMING,
            source_reference=result.id,
            confidence=confidence,
            metadata={"supporting_evidence_ids": hypothesis.get("supporting_evidence_ids", [])},
        )
        return str(record.id)

    @staticmethod
    def _result_json(analysis: DreamingAnalysis) -> str:
        review = analysis.daily_review
        wins = list(review.wins) if review else []
        payload = {
            "summary": wins[0] if wins else "最近 7 天的线索已经整理完成。",
            "wins": wins,
            "ideas": list(review.ideas) if review else [],
            "blockers": list(review.blockers) if review else [],
            "open_loops": list(review.open_loops) if review else [],
            "tomorrow_step": review.tomorrow_step if review else None,
            "hypotheses": [
                {
                    "statement": item.statement,
                    "confidence_band": item.confidence_band,
                    "supporting_evidence_ids": list(item.supporting_evidence_ids),
                    "open_questions": list(item.open_questions),
                }
                for item in analysis.hypotheses
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _result_payload(result) -> dict[str, object]:
        return {
            "id": result.id,
            "local_date": result.local_date,
            "version": result.version,
            "updated_at": result.updated_at,
            **json.loads(result.result_json),
        }
