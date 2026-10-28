from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.memory.base import MemoryContext
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.daily_review import DailyReviewDraft
from careerpilot.memory.dreaming import DreamingAnalysis, DreamingSnapshot, DreamingTrigger
from tests.api.auth_helpers import build_auth_service, issue_session


def test_daily_review_api_is_owner_scoped(tmp_path) -> None:
    cognitive = SqliteCognitiveStore(tmp_path / "memory.db")
    snapshot = DreamingSnapshot.from_turn(
        user_id="550e8400-e29b-41d4-a716-446655440000",
        conversation_id="c1",
        trigger=DreamingTrigger.MANUAL_REVIEW,
        user_message="今天修改了简历",
        assistant_message="记录下来",
        memories=MemoryContext(),
    )
    cognitive.enqueue(snapshot)
    job = cognitive.claim_next()
    assert job is not None
    cognitive.complete_analysis(
        job,
        DreamingAnalysis(
            daily_review=DailyReviewDraft(
                local_date="2026-10-24",
                wins=("修改简历",),
                ideas=(),
                blockers=(),
                open_loops=(),
                tomorrow_step="投递一个岗位",
                source_event_ids=(snapshot.evidence[0].id,),
            )
        ),
    )
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(create_app(cognitive_store=cognitive, auth_service=auth))
    owner_a = issue_session(auth, owner_id="550e8400-e29b-41d4-a716-446655440000")
    owner_b = issue_session(auth, owner_id="550e8400-e29b-41d4-a716-446655440001")
    try:
        assert client.get(
            "/v1/me/daily-reviews/2026-10-24", cookies=owner_a
        ).json()["wins"] == ["修改简历"]
        assert client.get("/v1/me/daily-reviews", cookies=owner_a).json()["items"][0][
            "local_date"
        ] == "2026-10-24"
        assert (
            client.get("/v1/me/daily-reviews/2026-10-24", cookies=owner_b).status_code
            == 404
        )
    finally:
        cognitive.close()
