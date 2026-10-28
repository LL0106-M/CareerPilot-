from dataclasses import dataclass

from fastapi.testclient import TestClient

from careerpilot.agent.service import ChatCommand, ChatResult, ChatStreamEvent
from careerpilot.api.app import create_app
from careerpilot.config import Settings
from careerpilot.context.contracts import RetrievalSource, TaskIntent
from careerpilot.support.policy import SupportMode
from tests.api.auth_helpers import build_auth_service, issue_session

OWNER_A = "550e8400-e29b-41d4-a716-446655440000"
OWNER_B = "550e8400-e29b-41d4-a716-446655440001"


def authenticated_client(tmp_path, service, settings=None, *, owner_id=OWNER_A):
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(
        create_app(settings=settings, chat_service=service, auth_service=auth)
    )
    client.cookies.update(issue_session(auth, owner_id=owner_id))
    return client, auth


@dataclass
class StubChatService:
    received: ChatCommand | None = None

    async def chat(self, command: ChatCommand) -> ChatResult:
        self.received = command
        return ChatResult(
            conversation_id=command.conversation_id,
            run_id="run-1",
            result_status="completed",
            citation_ids=(),
            citation_warnings=(),
            reply="这次被拒确实很难受，我们先不用急着证明什么。",
            support_mode=SupportMode.LISTEN,
            primary_intent=TaskIntent.EMOTIONAL_SUPPORT,
            retrieval_sources=(RetrievalSource.MEMORY,),
            memory_read_status="available",
            memory_write_status="accepted",
            dreaming_status="queued",
            memory_ids=(),
        )

    async def stream_chat(self, command: ChatCommand):
        self.received = command
        result = await self.chat(command)
        yield ChatStreamEvent(type="delta", text="这次被拒")
        yield ChatStreamEvent(type="delta", text="确实很难受，我们先不用急着证明什么。")
        yield ChatStreamEvent(type="completed", result=result)


def test_chat_returns_agent_reply_and_transparent_memory_status(tmp_path) -> None:
    service = StubChatService()
    client, _ = authenticated_client(tmp_path, service)

    response = client.post(
        "/v1/chat",
        json={
            "conversation_id": "thread-1",
            "message": "我被拒了，只想先说说",
            "support_mode": "listen",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": "thread-1",
        "run_id": "run-1",
        "result_status": "completed",
        "citation_ids": [],
        "citation_warnings": [],
        "reply": "这次被拒确实很难受，我们先不用急着证明什么。",
        "support_mode": "listen",
        "primary_intent": "emotional_support",
        "retrieval_sources": ["memory"],
        "memory_read_status": "available",
        "memory_write_status": "accepted",
        "dreaming_status": "queued",
        "memory_ids": [],
    }
    # owner_id is server-derived from cookie — cannot be overridden by client.
    assert service.received is not None
    assert service.received.user_id is not None
    assert service.received.conversation_id == "thread-1"
    assert service.received.message == "我被拒了，只想先说说"
    assert service.received.requested_mode == SupportMode.LISTEN


def test_chat_stream_emits_deltas_then_persists_completed_turn(tmp_path) -> None:
    service = StubChatService()
    settings = Settings(
        CAREERPILOT_SESSION_DB_PATH=tmp_path / "sessions.db",
        CAREERPILOT_MEMORY_DB_PATH=tmp_path / "memory.db",
        CAREERPILOT_RAG_DB_PATH=tmp_path / "rag.db",
        CAREERPILOT_PRODUCT_DB_PATH=tmp_path / "product.db",
        CAREERPILOT_ACTION_DB_PATH=tmp_path / "actions.db",
    )
    client, _ = authenticated_client(tmp_path, service, settings)

    response = client.post(
        "/v1/chat/stream",
        json={"message": "我被拒了，只想先说说"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: delta\ndata: {"text":"这次被拒"}' in response.text
    assert "event: completed" in response.text
    listed = client.get("/v1/me/conversations").json()["items"]
    assert listed[0]["title"] == "我被拒了，只想先说说"
    assert listed[0]["message_count"] == 2


def test_chat_rejects_empty_message_before_agent_runs(tmp_path) -> None:
    service = StubChatService()
    client, _ = authenticated_client(tmp_path, service)

    response = client.post(
        "/v1/chat",
        json={"conversation_id": "thread-1", "message": ""},
    )

    assert response.status_code == 422
    assert service.received is None


def test_chat_requires_login_before_agent_runs(tmp_path) -> None:
    service = StubChatService()
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(create_app(chat_service=service, auth_service=auth))

    response = client.post("/v1/chat", json={"message": "你好"})

    assert response.status_code == 401
    assert service.received is None


def test_chat_uses_authenticated_account_as_owner(tmp_path) -> None:
    service = StubChatService()
    client, _ = authenticated_client(tmp_path, service)

    response = client.post(
        "/v1/chat",
        json={"message": "再聊一句"},
    )

    assert response.status_code == 200
    assert service.received is not None
    assert service.received.user_id == OWNER_A


def test_chat_ignores_client_supplied_user_id(tmp_path) -> None:
    service = StubChatService()
    client, _ = authenticated_client(tmp_path, service)

    response = client.post(
        "/v1/chat",
        json={
            "user_id": "i-am-a-troll",  # Pydantic will reject as unknown field
            "message": "试图冒充别人",
        },
    )

    # FastAPI Pydantic rejects unknown field by default → 422.
    # Either way, client-supplied user_id never reaches the stub.
    assert response.status_code == 422
    assert service.received is None


def test_successful_chat_is_listed_and_can_be_reopened(tmp_path) -> None:
    service = StubChatService()
    settings = Settings(
        CAREERPILOT_SESSION_DB_PATH=tmp_path / "sessions.db",
        CAREERPILOT_MEMORY_DB_PATH=tmp_path / "memory.db",
        CAREERPILOT_RAG_DB_PATH=tmp_path / "rag.db",
        CAREERPILOT_PRODUCT_DB_PATH=tmp_path / "product.db",
        CAREERPILOT_ACTION_DB_PATH=tmp_path / "actions.db",
    )
    client, _ = authenticated_client(tmp_path, service, settings)

    sent = client.post("/v1/chat", json={"message": "我想了解 AI 产品经理"})
    conversation_id = sent.json()["conversation_id"]

    listed = client.get("/v1/me/conversations")
    reopened = client.get(f"/v1/me/conversations/{conversation_id}")

    assert listed.status_code == 200
    assert listed.json()["items"] == [
        {
            "id": conversation_id,
            "title": "我想了解 AI 产品经理",
            "updated_at": listed.json()["items"][0]["updated_at"],
            "message_count": 2,
        }
    ]
    assert reopened.status_code == 200
    assert reopened.json() == {
        "id": conversation_id,
        "title": "我想了解 AI 产品经理",
        "updated_at": listed.json()["items"][0]["updated_at"],
        "messages": [
            {"role": "user", "content": "我想了解 AI 产品经理"},
            {"role": "agent", "content": "这次被拒确实很难受，我们先不用急着证明什么。"},
        ],
    }


def test_conversation_history_is_owner_scoped(tmp_path) -> None:
    settings = Settings(
        CAREERPILOT_SESSION_DB_PATH=tmp_path / "sessions.db",
        CAREERPILOT_MEMORY_DB_PATH=tmp_path / "memory.db",
        CAREERPILOT_RAG_DB_PATH=tmp_path / "rag.db",
        CAREERPILOT_PRODUCT_DB_PATH=tmp_path / "product.db",
        CAREERPILOT_ACTION_DB_PATH=tmp_path / "actions.db",
    )
    auth = build_auth_service(tmp_path / "auth.db")
    first = TestClient(
        create_app(settings=settings, chat_service=StubChatService(), auth_service=auth)
    )
    second = TestClient(
        create_app(settings=settings, chat_service=StubChatService(), auth_service=auth)
    )
    first.cookies.update(issue_session(auth, owner_id=OWNER_A))
    second.cookies.update(issue_session(auth, owner_id=OWNER_B))
    conversation_id = first.post("/v1/chat", json={"message": "只属于第一个用户"}).json()[
        "conversation_id"
    ]

    assert second.get("/v1/me/conversations").json() == {"items": []}
    assert second.get(f"/v1/me/conversations/{conversation_id}").status_code == 404
