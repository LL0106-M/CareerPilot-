from dataclasses import dataclass

from fastapi.testclient import TestClient

from careerpilot.agent.service import ChatCommand, ChatResult
from careerpilot.api.app import create_app
from careerpilot.context.contracts import TaskIntent
from careerpilot.product_store import ProductStore
from careerpilot.support.policy import SupportMode
from tests.api.auth_helpers import build_auth_service, issue_session


@dataclass
class CalendarChatService:
    async def chat(self, command: ChatCommand) -> ChatResult:
        return ChatResult(
            conversation_id=command.conversation_id,
            run_id="run-calendar",
            result_status="completed",
            citation_ids=(),
            citation_warnings=(),
            reply="已经记下了。",
            support_mode=SupportMode.ACT,
            primary_intent=TaskIntent.CALENDAR_MANAGEMENT,
            retrieval_sources=(),
            memory_read_status="skipped",
            memory_write_status="skipped",
            dreaming_status="skipped",
        )


@dataclass
class ListenModeCalendarChatService(CalendarChatService):
    async def chat(self, command: ChatCommand) -> ChatResult:
        result = await super().chat(command)
        return ChatResult(
            conversation_id=result.conversation_id,
            run_id=result.run_id,
            result_status=result.result_status,
            citation_ids=result.citation_ids,
            citation_warnings=result.citation_warnings,
            reply=result.reply,
            support_mode=SupportMode.LISTEN,
            primary_intent=result.primary_intent,
            retrieval_sources=result.retrieval_sources,
            memory_read_status=result.memory_read_status,
            memory_write_status=result.memory_write_status,
            dreaming_status=result.dreaming_status,
        )


@dataclass
class PartialCalendarChatService(CalendarChatService):
    async def chat(self, command: ChatCommand) -> ChatResult:
        result = await super().chat(command)
        return ChatResult(
            conversation_id=result.conversation_id,
            run_id=result.run_id,
            result_status="partial",
            citation_ids=result.citation_ids,
            citation_warnings=result.citation_warnings,
            reply=result.reply,
            support_mode=result.support_mode,
            primary_intent=result.primary_intent,
            retrieval_sources=result.retrieval_sources,
            memory_read_status=result.memory_read_status,
            memory_write_status=result.memory_write_status,
            dreaming_status=result.dreaming_status,
        )


def build_client(tmp_path, *, chat_service=None):
    products = ProductStore(tmp_path / "product.db")
    auth = build_auth_service(tmp_path / "auth.db")
    owner = "550e8400-e29b-41d4-a716-446655440000"
    client = TestClient(
        create_app(
            product_store=products,
            auth_service=auth,
            chat_service=chat_service,
        )
    )
    client.cookies.update(issue_session(auth, owner_id=owner))
    return client, products


def test_manual_calendar_event_appears_in_dashboard(tmp_path) -> None:
    client, products = build_client(tmp_path)
    try:
        response = client.post(
            "/v1/me/journey",
            json={
                "title": "腾讯产品二面",
                "start_at": "2026-10-30T15:00:00+08:00",
                "end_at": "2026-10-30T16:00:00+08:00",
                "reminder_minutes": 30,
                "meeting_url": "https://meeting.tencent.com/dm/abc",
                "notes": "准备三个项目案例",
            },
        )

        assert response.status_code == 201
        assert response.json()["created_via"] == "manual"
        assert client.get("/v1/me/dashboard").json()["journey"][0]["title"] == "腾讯产品二面"
    finally:
        products.close()


def test_calendar_event_rejects_invalid_range_and_meeting_scheme(tmp_path) -> None:
    client, products = build_client(tmp_path)
    try:
        response = client.post(
            "/v1/me/journey",
            json={
                "title": "错误日程",
                "start_at": "2026-10-30T16:00:00+08:00",
                "end_at": "2026-10-30T15:00:00+08:00",
                "meeting_url": "http://meeting.example.com/abc",
            },
        )

        assert response.status_code == 422
        assert client.get("/v1/me/dashboard").json()["journey"] == []
    finally:
        products.close()


def test_explicit_chat_reminder_creates_the_same_local_calendar_event(tmp_path) -> None:
    client, products = build_client(tmp_path, chat_service=CalendarChatService())
    try:
        response = client.post(
            "/v1/chat",
            json={
                "message": "提醒我2026-10-30下午3点参加腾讯产品二面，提前30分钟提醒，"
                "会议链接 https://meeting.tencent.com/dm/abc"
            },
        )

        assert response.status_code == 200
        event = client.get("/v1/me/dashboard").json()["journey"][0]
        assert event["title"] == "参加腾讯产品二面"
        assert event["created_via"] == "chat"
        assert event["reminder_minutes"] == 30
    finally:
        products.close()


def test_listen_mode_never_creates_calendar_side_effects(tmp_path) -> None:
    client, products = build_client(tmp_path, chat_service=ListenModeCalendarChatService())
    try:
        response = client.post(
            "/v1/chat",
            json={"message": "提醒我2026-10-30下午3点参加面试"},
        )

        assert response.status_code == 200
        assert client.get("/v1/me/dashboard").json()["journey"] == []
    finally:
        products.close()


def test_chat_calendar_write_is_idempotent_by_run_id(tmp_path) -> None:
    client, products = build_client(tmp_path, chat_service=CalendarChatService())
    payload = {"message": "提醒我2026-10-30下午3点参加面试"}
    try:
        assert client.post("/v1/chat", json=payload).status_code == 200
        assert client.post("/v1/chat", json=payload).status_code == 200

        assert len(client.get("/v1/me/dashboard").json()["journey"]) == 1
    finally:
        products.close()


def test_partial_chat_turn_does_not_create_calendar_side_effect(tmp_path) -> None:
    client, products = build_client(tmp_path, chat_service=PartialCalendarChatService())
    try:
        assert client.post(
            "/v1/chat", json={"message": "提醒我2026-10-30下午3点参加面试"}
        ).status_code == 200
        assert client.get("/v1/me/dashboard").json()["journey"] == []
    finally:
        products.close()


def test_invalid_chat_date_does_not_turn_completed_chat_into_server_error(tmp_path) -> None:
    client, products = build_client(tmp_path, chat_service=CalendarChatService())
    try:
        response = client.post(
            "/v1/chat", json={"message": "提醒我2026-02-30下午3点参加面试"}
        )

        assert response.status_code == 200
        assert client.get("/v1/me/dashboard").json()["journey"] == []
    finally:
        products.close()
