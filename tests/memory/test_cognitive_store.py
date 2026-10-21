import pytest

from careerpilot.memory.base import MemoryContext, MemoryItem
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.dreaming import (
    DreamingSnapshot,
    DreamingTrigger,
    HypothesisProposal,
)


def make_snapshot() -> DreamingSnapshot:
    return DreamingSnapshot.from_turn(
        user_id="u1",
        conversation_id="c1",
        trigger=DreamingTrigger.MANUAL_REVIEW,
        user_message="帮我复盘这次选择",
        assistant_message="我们一起看证据",
        memories=MemoryContext(facts=(MemoryItem("m1", "做过数据项目", "fact"),)),
    )


def test_enqueue_is_idempotent_and_claims_once(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    snapshot = make_snapshot()

    assert store.enqueue(snapshot) is True
    assert store.enqueue(snapshot) is False
    assert store.claim_next() is not None
    assert store.claim_next() is None


def test_complete_persists_candidate_hypothesis_with_snapshot_evidence(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    store.enqueue(make_snapshot())
    job = store.claim_next()
    assert job is not None

    store.complete(
        job,
        (
            HypothesisProposal(
                statement="用户可能喜欢数据驱动的工作",
                confidence_band="low",
                supporting_evidence_ids=("m1",),
                open_questions=("是否喜欢长期做数据分析？",),
            ),
        ),
    )

    hypotheses = store.list_hypotheses("u1")
    assert len(hypotheses) == 1
    assert hypotheses[0].status == "candidate"
    assert hypotheses[0].supporting_evidence_ids == ("m1",)


def test_complete_rejects_evidence_outside_snapshot_atomically(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    store.enqueue(make_snapshot())
    job = store.claim_next()
    assert job is not None

    with pytest.raises(ValueError, match="outside its snapshot"):
        store.complete(
            job,
            (
                HypothesisProposal(
                    statement="无依据猜测",
                    confidence_band="high",
                    supporting_evidence_ids=("foreign",),
                ),
            ),
        )

    assert store.list_hypotheses("u1") == ()


def test_poison_job_stops_retrying_after_three_failures(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    store.enqueue(make_snapshot())

    for _ in range(3):
        job = store.claim_next()
        assert job is not None
        store.fail(job, "invalid model output")

    assert store.claim_next() is None
