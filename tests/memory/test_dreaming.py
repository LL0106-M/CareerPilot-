import pytest

from careerpilot.memory.base import MemoryContext
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

