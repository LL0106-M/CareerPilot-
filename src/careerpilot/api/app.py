from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, HTTPException

from careerpilot.agent.service import ChatCommand, ChatResult
from careerpilot.api.dependencies import build_agent_service
from careerpilot.api.schemas import ChatRequest, ChatResponse
from careerpilot.config import Settings, get_settings
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.memos import MemosCloudMemoryStore
from careerpilot.rag.store import SqliteRagStore


class ChatService(Protocol):
    async def chat(self, command: ChatCommand) -> ChatResult: ...


def create_app(
    settings: Settings | None = None,
    chat_service: ChatService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    owned_memory_store: MemosCloudMemoryStore | None = None
    owned_rag_store: SqliteRagStore | None = None
    owned_cognitive_store: SqliteCognitiveStore | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_memory_store is not None:
            await owned_memory_store.aclose()
        if owned_rag_store is not None:
            owned_rag_store.close()
        if owned_cognitive_store is not None:
            owned_cognitive_store.close()

    app = FastAPI(title="CareerPilot Agent API", version="0.1.0", lifespan=lifespan)

    def resolve_chat_service() -> ChatService:
        nonlocal chat_service, owned_memory_store, owned_rag_store, owned_cognitive_store
        if chat_service is None:
            try:
                (
                    chat_service,
                    owned_memory_store,
                    owned_rag_store,
                    owned_cognitive_store,
                ) = build_agent_service(resolved_settings)
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return chat_service

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": resolved_settings.app_name}

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        service = resolve_chat_service()
        result = await service.chat(
            ChatCommand(
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                message=request.message,
                requested_mode=request.support_mode,
            )
        )
        return ChatResponse(
            reply=result.reply,
            support_mode=result.support_mode,
            memory_read_status=result.memory_read_status,
            memory_write_status=result.memory_write_status,
            dreaming_status=result.dreaming_status,
        )

    return app


app = create_app()
