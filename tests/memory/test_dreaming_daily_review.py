import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from careerpilot.memory.base import MemoryContext, MemoryItem
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.daily_review import DailyReviewDraft
from careerpilot.memory.dreaming import (
    DreamingAnalysis,
    DreamingSnapshot,
    DreamingTrigger,
    HypothesisProposal,
    MemoryPatchProposal,
)
from careerpilot.memory.dreaming_llm import JsonDreamingAnalyzer


def snapshot() -> DreamingSnapshot:
    return DreamingSnapshot.from_turn(
        user_id="u1",
        conversation_id="c1",
        trigger=DreamingTrigger.MANUAL_REVIEW,
        user_message="我今天想到做一个面试复盘工具，也完成了简历修改",
        assistant_message="这是一个值得记录的小胜利和想法",
        memories=MemoryContext(facts=(MemoryItem("m1", "正在求职", "fact"),)),
    )


def analysis() -> DreamingAnalysis:
    current_turn = snapshot().evidence[0].id
    return DreamingAnalysis(
        hypotheses=(
            HypothesisProposal(
                statement="用户可能愿意通过小工具验证产品想法",
                confidence_band="low",
                supporting_evidence_ids=(current_turn,),
            ),
        ),
        daily_review=DailyReviewDraft(
            local_date="2026-10-24",
            wins=("完成简历修改",),
            ideas=("做一个面试复盘工具",),
            blockers=(),
            open_loops=("验证是否有人需要",),
            tomorrow_step="访谈一位求职者",
            source_event_ids=(current_turn,),
        ),
        patches=(
            MemoryPatchProposal(
                operation="link",
                target_type="idea",
                content="把面试复盘工具关联到求职目标",
                supporting_evidence_ids=(current_turn,),
                requires_confirmation=False,
            ),
        ),
    )


def test_complete_analysis_publishes_review_and_patch_together(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    store.enqueue(snapshot())
    job = store.claim_next()
    assert job is not None

    store.complete_analysis(job, analysis())

    review = store.get_daily_review("u1", "2026-10-24")
    assert review is not None
    assert review.ideas == ("做一个面试复盘工具",)
    assert store.list_memory_patches("u1")[0].target_type == "idea"
    assert len(store.list_hypotheses("u1")) == 1


def test_invalid_analysis_does_not_partially_publish(tmp_path) -> None:
    store = SqliteCognitiveStore(tmp_path / "memory.db")
    store.enqueue(snapshot())
    job = store.claim_next()
    assert job is not None
    invalid = analysis()
    invalid = DreamingAnalysis(
        hypotheses=invalid.hypotheses,
        daily_review=invalid.daily_review,
        patches=(
            MemoryPatchProposal(
                operation="link",
                target_type="idea",
                content="无来源",
                supporting_evidence_ids=("foreign",),
                requires_confirmation=False,
            ),
        ),
    )

    with pytest.raises(ValueError, match="outside its snapshot"):
        store.complete_analysis(job, invalid)

    assert store.get_daily_review("u1", "2026-10-24") is None
    assert store.list_memory_patches("u1") == ()
    assert store.list_hypotheses("u1") == ()


@pytest.mark.asyncio
async def test_json_analyzer_parses_daily_review_and_patches() -> None:
    evidence_id = snapshot().evidence[0].id
    payload = {
        "hypotheses": [],
        "daily_review": {
            "local_date": "2026-10-24",
            "wins": ["完成简历修改"],
            "ideas": ["面试复盘工具"],
            "blockers": [],
            "open_loops": ["验证需求"],
            "tomorrow_step": "访谈一人",
            "source_event_ids": [evidence_id],
        },
        "patches": [
            {
                "operation": "link",
                "target_type": "idea",
                "content": "关联求职目标",
                "supporting_evidence_ids": [evidence_id],
                "requires_confirmation": False,
            }
        ],
    }
    import json

    model = FakeMessagesListChatModel(responses=[AIMessage(content=json.dumps(payload))])

    result = await JsonDreamingAnalyzer(model).analyze(snapshot())

    assert isinstance(result, DreamingAnalysis)
    assert result.daily_review is not None
    assert result.daily_review.tomorrow_step == "访谈一人"
    assert result.patches[0].requires_confirmation is False
