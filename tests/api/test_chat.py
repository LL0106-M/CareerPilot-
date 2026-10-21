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
        )


def test_chat_returns_agent_reply_and_transparent_memory_status() -> None:
    service = StubChatService()
    client = TestClient(create_app(chat_service=service))

    response = client.post(
        "/v1/chat",
        json={
            "user_id": "user-1",
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
    }
    assert service.received == ChatCommand(
        user_id="user-1",
        conversation_id="thread-1",
        message="我被拒了，只想先说说",
        requested_mode=SupportMode.LISTEN,
    )


def test_chat_rejects_empty_message_before_agent_runs() -> None:
    service = StubChatService()
    client = TestClient(create_app(chat_service=service))

    response = client.post(
        "/v1/chat",
        json={"user_id": "user-1", "conversation_id": "thread-1", "message": ""},
    )

    assert response.status_code == 422
    assert service.received is None
