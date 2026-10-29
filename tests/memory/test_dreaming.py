import pytest

from careerpilot.memory.base import MemoryContext
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.dreaming import (
    DreamingProcessor,
    DreamingSnapshot,
    DreamingTrigger,
    DreamingTriggerPolicy,
    HypothesisProposal,
)


@pytest.mark.parametrize("message", ["帮我复盘这段经历", "我们回顾一下职业探索"])
def test_manual_reflection_triggers_dreaming(message: str) -> None:
    assert DreamingTriggerPolicy().detect(message) is DreamingTrigger.MANUAL_REVIEW


@pytest.mark.parametrize("message", ["今天面试结束了", "刚收到 offer", "我被拒了"])
def test_career_milestone_triggers_dreaming(message: str) -> None:
    assert DreamingTriggerPolicy().detect(message) is DreamingTrigger.CAREER_MILESTONE


def test_ordinary_turn_does_not_trigger_dreaming() -> None:
    assert DreamingTriggerPolicy().detect("产品经理需要哪些能力") is None


class RecordingStore:
    def __init__(self, job=None) -> None:
        self.job = job
        self.completed = None
        self.failed = None

    def claim_next(self):
        job, self.job = self.job, None
        return job

    def complete(self, job, proposals) -> None:
        self.completed = (job, proposals)

    def fail(self, job, error: str) -> None:
        self.failed = (job, error)


class StaticAnalyzer:
    async def analyze(self, snapshot):
        return (
            HypothesisProposal(
                statement="用户可能更重视工作节奏",
                confidence_band="low",
                supporting_evidence_ids=(snapshot.evidence[0].id,),
            ),
        )


@pytest.mark.asyncio
async def test_processor_completes_claimed_job() -> None:
    from careerpilot.memory.dreaming import DreamingJob

    snapshot = DreamingSnapshot.from_turn(
        user_id="u1",
        conversation_id="c1",
        trigger=DreamingTrigger.MANUAL_REVIEW,
        user_message="帮我复盘",
        assistant_message="好",
        memories=MemoryContext(),
    )
    job = DreamingJob("j1", snapshot, 0)
    store = RecordingStore(job)

    assert await DreamingProcessor(store, StaticAnalyzer()).run_once() is True
    assert store.completed is not None


def test_manual_dreaming_reuses_active_job_and_overwrites_daily_result(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    first = store.start_manual_job("u1", "2026-10-29", '[{"id":"e1"}]')
    same = store.start_manual_job("u1", "2026-10-29", '[{"id":"e1"}]')
    assert same.id == first.id

    store.complete_manual_job("u1", first.id, '{"summary":"第一次","hypotheses":[]}')
    initial = store.get_manual_result("u1", "2026-10-29")
    assert initial is not None
    assert initial.version == 1

    regenerated = store.start_manual_job("u1", "2026-10-29", '[{"id":"e2"}]')
    assert regenerated.id == first.id
    assert regenerated.status == "queued"
    store.complete_manual_job("u1", regenerated.id, '{"summary":"更新后","hypotheses":[]}')
    updated = store.get_manual_result("u1", "2026-10-29")
    assert updated is not None
    assert updated.version == 2
    assert "更新后" in updated.result_json


def test_failed_manual_regeneration_preserves_published_result_and_owner_scope(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    job = store.start_manual_job("u1", "2026-10-29", "[]")
    store.complete_manual_job("u1", job.id, '{"summary":"保留我"}')
    retry = store.start_manual_job("u1", "2026-10-29", "[]")
    store.fail_manual_job("u1", retry.id, "model unavailable")

    preserved = store.get_manual_result("u1", "2026-10-29")
    assert preserved is not None and "保留我" in preserved.result_json
    assert store.get_manual_job("u2", retry.id) is None
    assert store.get_manual_result("u2", "2026-10-29") is None
