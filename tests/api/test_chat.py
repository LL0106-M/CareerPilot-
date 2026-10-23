from dataclasses import dataclass

from fastapi.testclient import TestClient

from careerpilot.agent.service import ChatCommand, ChatResult
from careerpilot.api.app import create_app
from careerpilot.support.policy import SupportMode


@dataclass
class StubChatService:
    received: ChatCommand | None = None

    async def chat(self, command: ChatCommand) -> ChatResult:
        self.received = command
        return ChatResult(
            reply="这次被拒确实很难受，我们先不用急着证明什么。",
            support_mode=SupportMode.LISTEN,
            memory_read_status="available",
            memory_write_status="accepted",
            dreaming_status="queued",
        )


def test_chat_returns_agent_reply_and_transparent_memory_status() -> None:
    service = StubChatService()
    client = TestClient(create_app(chat_service=service))

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
        "reply": "这次被拒确实很难受，我们先不用急着证明什么。",
        "support_mode": "listen",
        "memory_read_status": "available",
        "memory_write_status": "accepted",
        "dreaming_status": "queued",
    }
    # owner_id is server-derived from cookie — cannot be overridden by client.
    assert service.received is not None
    assert service.received.user_id is not None
    assert service.received.conversation_id == "thread-1"
    assert service.received.message == "我被拒了，只想先说说"
    assert service.received.requested_mode == SupportMode.LISTEN


def test_chat_rejects_empty_message_before_agent_runs() -> None:
    service = StubChatService()
    client = TestClient(create_app(chat_service=service))

    response = client.post(
        "/v1/chat",
        json={"conversation_id": "thread-1", "message": ""},
    )

    assert response.status_code == 422
    assert service.received is None


def test_chat_issues_owner_cookie_on_first_request() -> None:
    service = StubChatService()
    client = TestClient(create_app(chat_service=service))

    response = client.post("/v1/chat", json={"message": "你好"})

    assert response.status_code == 200
    owner_cookie = response.cookies.get("careerpilot_owner")
    assert owner_cookie is not None
    owner_id, signature = owner_cookie.rsplit(".", 1)
    assert owner_id
    assert signature
    assert service.received is not None
    assert service.received.user_id == owner_id
    assert service.received.conversation_id is not None


def test_chat_reuses_owner_when_cookie_present() -> None:
    service = StubChatService()
    client = TestClient(create_app(chat_service=service))
    owner = "550e8400-e29b-41d4-a716-446655440000"

    response = client.post(
        "/v1/chat",
        json={"message": "再聊一句"},
        cookies={"careerpilot_owner": owner},
    )

    assert response.status_code == 200
    assert service.received is not None
    assert service.received.user_id == owner


def test_chat_ignores_client_supplied_user_id() -> None:
    service = StubChatService()
    client = TestClient(create_app(chat_service=service))
    owner = "550e8400-e29b-41d4-a716-446655440000"

    response = client.post(
        "/v1/chat",
        json={
            "user_id": "i-am-a-troll",  # Pydantic will reject as unknown field
            "message": "试图冒充别人",
        },
        cookies={"careerpilot_owner": owner},
    )

    # FastAPI Pydantic rejects unknown field by default → 422.
    # Either way, client-supplied user_id never reaches the stub.
    assert response.status_code == 422
    assert service.received is None
