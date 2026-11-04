from dataclasses import dataclass

from fastapi.testclient import TestClient

from careerpilot.agent.service import ChatCommand, ChatResult, ChatStreamEvent
from careerpilot.api.app import create_app
from careerpilot.config import Settings
from careerpilot.context.contracts import TaskIntent
from careerpilot.memory.direction_signals import (
    DirectionExplicitness,
    DirectionSignal,
    DirectionSignalAction,
)
from careerpilot.product_store import ProductStore
from careerpilot.support.policy import SupportMode
from tests.api.auth_helpers import build_auth_service, issue_session


OWNER_A = "550e8400-e29b-41d4-a716-446655440010"
OWNER_B = "550e8400-e29b-41d4-a716-446655440011"


def settings(tmp_path) -> Settings:
    return Settings(
        CAREERPILOT_SESSION_DB_PATH=tmp_path / "sessions.db",
        CAREERPILOT_MEMORY_DB_PATH=tmp_path / "memory.db",
        CAREERPILOT_RAG_DB_PATH=tmp_path / "rag.db",
        CAREERPILOT_PRODUCT_DB_PATH=tmp_path / "product.db",
        CAREERPILOT_ACTION_DB_PATH=tmp_path / "actions.db",
    )


@dataclass
class DirectionChatService:
    signal: DirectionSignal

    async def chat(self, command: ChatCommand) -> ChatResult:
        return self._result(command)

    async def stream_chat(self, command: ChatCommand):
        result = self._result(command)
        yield ChatStreamEvent(type="delta", text=result.reply)
        yield ChatStreamEvent(type="completed", result=result)

    def _result(self, command: ChatCommand) -> ChatResult:
        return ChatResult(
            conversation_id=command.conversation_id,
            run_id="run-direction-1",
            result_status="completed",
            citation_ids=(),
            citation_warnings=(),
            reply="我听到了这条方向线索。",
            support_mode=SupportMode.ORGANIZE,
            primary_intent=TaskIntent.CAREER_DIRECTION,
            retrieval_sources=(),
            memory_read_status="skipped",
            memory_write_status="skipped",
            dreaming_status="skipped",
            direction_signal=self.signal,
        )


def test_product_store_keeps_implicit_signal_pending_until_acceptance(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        signal = store.record_direction_signal(
            OWNER_A,
            source_run_id="run-implicit",
            label="平台型产品工作",
            explicitness="implicit",
            source_quote="最近总是在关注平台型产品",
            reason="持续关注但未明确选择",
            confidence=0.76,
        )

        assert signal["status"] == "pending"
        assert store.list_directions(OWNER_A) == []

        direction = store.accept_direction_signal(OWNER_A, signal["id"])
        repeated = store.accept_direction_signal(OWNER_A, signal["id"])

        assert direction is not None
        assert direction["status"] == "confirmed"
        assert repeated == direction
        assert store.list_directions(OWNER_A) == [direction]
        assert store.list_directions(OWNER_B) == []
        assert store.accept_direction_signal(OWNER_B, signal["id"]) is None
    finally:
        store.close()


def test_product_store_auto_confirms_explicit_signal_without_creating_journey(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        signal = store.record_direction_signal(
            OWNER_A,
            source_run_id="run-explicit",
            label="用户明确表达的方向",
            explicitness="explicit",
            source_quote="我确定要推进这个方向",
            reason="用户明确表达",
            confidence=0.99,
        )

        assert signal["status"] == "accepted"
        assert store.list_directions(OWNER_A)[0]["label"] == "用户明确表达的方向"
        assert store.dashboard(OWNER_A)["journey"] == []
    finally:
        store.close()


def test_chat_persists_explicit_direction_and_returns_server_signal_id(tmp_path) -> None:
    signal = DirectionSignal(
        explicitness=DirectionExplicitness.EXPLICIT,
        action=DirectionSignalAction.ADD_TO_COMPASS,
        label="用户明确表达的方向",
        source_quote="我确定要推进这个方向",
        reason="用户明确表达",
        confidence=0.99,
    )
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(
        create_app(
            settings=settings(tmp_path),
            chat_service=DirectionChatService(signal),
            auth_service=auth,
        )
    )
    client.cookies.update(issue_session(auth, owner_id=OWNER_A))

    response = client.post("/v1/chat", json={"message": "我确定要推进这个方向"})

    assert response.status_code == 200
    payload = response.json()["direction_signal"]
    assert payload["id"].startswith("signal-")
    assert payload["status"] == "accepted"
    dashboard = client.get("/v1/me/dashboard").json()
    assert [item["label"] for item in dashboard["directions"]] == ["用户明确表达的方向"]
    assert dashboard["journey"] == []


def test_accept_direction_signal_is_owner_scoped(tmp_path) -> None:
    product = ProductStore(tmp_path / "product.db")
    signal = product.record_direction_signal(
        OWNER_A,
        source_run_id="run-owner",
        label="候选方向",
        explicitness="implicit",
        source_quote="我最近总在关注这个方向",
        reason="隐含兴趣",
        confidence=0.7,
    )
    auth = build_auth_service(tmp_path / "auth.db")
    app = create_app(settings=settings(tmp_path), product_store=product, auth_service=auth)
    client = TestClient(app)
    client.cookies.update(issue_session(auth, owner_id=OWNER_B))

    response = client.post(f"/v1/me/direction-signals/{signal['id']}/accept")

    assert response.status_code == 404
    assert product.list_directions(OWNER_A) == []


def test_direction_journey_endpoint_requires_owner_and_reuses_existing_journey(tmp_path) -> None:
    product = ProductStore(tmp_path / "product.db")
    product.record_direction_signal(
        OWNER_A,
        source_run_id="run-journey",
        label="新能源产品经理",
        explicitness="explicit",
        source_quote="我想申请新能源产品经理",
        reason="明确申请意图",
        confidence=0.96,
    )
    direction = product.list_directions(OWNER_A)[0]
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(create_app(product_store=product, auth_service=auth))

    denied = client.post(
        f"/v1/me/directions/{direction['id']}/journey",
        cookies=issue_session(auth, owner_id=OWNER_B),
    )
    first = client.post(
        f"/v1/me/directions/{direction['id']}/journey",
        cookies=issue_session(auth, owner_id=OWNER_A),
    )
    repeated = client.post(
        f"/v1/me/directions/{direction['id']}/journey",
        cookies=issue_session(auth, owner_id=OWNER_A),
    )

    assert denied.status_code == 404
    assert first.status_code == 201
    assert repeated.status_code == 201
    assert repeated.json() == first.json()
    assert len(first.json()["tasks"]) == 3
    assert {job["purpose"] for job in first.json()["collection_jobs"]} == {
        "job_opportunity",
        "interview_archive",
        "learning_resource",
    }
    product.close()
