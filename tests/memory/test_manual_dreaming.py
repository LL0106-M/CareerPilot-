from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.daily_review import DailyReviewDraft
from careerpilot.memory.dreaming import DreamingAnalysis, EvidenceRef, HypothesisProposal
from careerpilot.memory.manual_dreaming import (
    ManualDreamingNoEvidence,
    ManualDreamingService,
    collect_recent_evidence,
)


class StaticAnalyzer:
    async def analyze(self, snapshot):
        return DreamingAnalysis(
            hypotheses=(HypothesisProposal("更适合产品探索", "medium", (snapshot.evidence[0].id,)),),
            daily_review=DailyReviewDraft(
                local_date="2026-10-29", wins=("持续记录",), ideas=("验证产品方向",),
                blockers=(), open_loops=("需要真实访谈",), tomorrow_step="约一位用户访谈",
                source_event_ids=(snapshot.evidence[0].id,),
            ),
        )


class RecordingMemories:
    def __init__(self, records=()):
        self.records = records
        self.proposed = []

    def list(self, owner_id, **kwargs):
        return self.records

    def propose(self, **kwargs):
        self.proposed.append(kwargs)
        return SimpleNamespace(id="hypothesis-1")


class EmptyProduct:
    def list_conversations(self, owner_id):
        return []


class EmptyRag:
    def list_user_documents(self, owner_id):
        return ()


def test_collector_keeps_only_evidence_from_the_last_seven_days() -> None:
    now = datetime(2026, 10, 29, tzinfo=UTC)
    memories = RecordingMemories((
        SimpleNamespace(id="recent", content="最近想法", type=SimpleNamespace(value="idea"), updated_at=now - timedelta(days=6)),
        SimpleNamespace(id="old", content="旧想法", type=SimpleNamespace(value="idea"), updated_at=now - timedelta(days=8)),
    ))
    evidence = collect_recent_evidence("u1", date(2026, 10, 29), memories, EmptyProduct(), EmptyRag())
    assert [item.id for item in evidence] == ["memory:recent"]


@pytest.mark.asyncio
async def test_manual_service_generates_result_and_confirms_hypothesis(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    memories = RecordingMemories()
    service = ManualDreamingService(
        store, StaticAnalyzer(), memories,
        lambda owner_id, local_day: (EvidenceRef("e1", "我想验证产品方向", "idea"),),
    )
    job = service.start("u1", date(2026, 10, 29))
    await service.run("u1", job.id)
    status = service.status("u1", job.id)
    assert status is not None and status["status"] == "completed"
    assert status["result"]["summary"] == "持续记录"

    memory_id = service.confirm_hypothesis("u1", status["result"]["id"], 0)
    assert memory_id == "hypothesis-1"
    assert memories.proposed[0]["content"] == "更适合产品探索"


def test_manual_service_rejects_empty_evidence(tmp_path) -> None:
    service = ManualDreamingService(
        SqliteCognitiveStore(tmp_path / "memory.db"), StaticAnalyzer(), RecordingMemories(),
        lambda owner_id, local_day: (),
    )
    with pytest.raises(ManualDreamingNoEvidence):
        service.start("u1", date(2026, 10, 29))


@pytest.mark.asyncio
async def test_manual_service_records_analyzer_failure(tmp_path) -> None:
    class BrokenAnalyzer:
        async def analyze(self, snapshot):
            raise RuntimeError("offline")

    store = SqliteCognitiveStore(tmp_path / "memory.db")
    service = ManualDreamingService(
        store, BrokenAnalyzer(), RecordingMemories(),
        lambda owner_id, local_day: (EvidenceRef("e1", "证据", "idea"),),
    )
    job = service.start("u1", date(2026, 10, 29))
    with pytest.raises(RuntimeError):
        await service.run("u1", job.id)
    assert store.get_manual_job("u1", job.id).status == "failed"
