from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, HTTPException, Query

from careerpilot.agent.service import ChatCommand, ChatResult
from careerpilot.api.dependencies import build_agent_service
from careerpilot.api.schemas import ChatRequest, ChatResponse
from careerpilot.config import Settings, get_settings
from careerpilot.harness.session import SqliteSessionStore
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.memos import MemosCloudMemoryStore
from careerpilot.rag.store import SqliteRagStore


class ChatService(Protocol):
    async def chat(self, command: ChatCommand) -> ChatResult: ...


def create_app(
    settings: Settings | None = None,
    chat_service: ChatService | None = None,
    rag_store: SqliteRagStore | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    owned_memory_store: MemosCloudMemoryStore | None = None
    owned_rag_store: SqliteRagStore | None = None
    owned_cognitive_store: SqliteCognitiveStore | None = None
    owned_session_store: SqliteSessionStore | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_memory_store is not None:
            await owned_memory_store.aclose()
        if owned_rag_store is not None:
            owned_rag_store.close()
        if owned_cognitive_store is not None:
            owned_cognitive_store.close()
        if owned_session_store is not None:
            owned_session_store.close()

    app = FastAPI(title="CareerPilot Agent API", version="0.1.0", lifespan=lifespan)

    def resolve_chat_service() -> ChatService:
        nonlocal chat_service, owned_memory_store, owned_rag_store
        nonlocal owned_cognitive_store, owned_session_store
        if chat_service is None:
            try:
                (
                    chat_service,
                    owned_memory_store,
                    owned_rag_store,
                    owned_cognitive_store,
                    owned_session_store,
                ) = build_agent_service(resolved_settings)
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return chat_service

    def resolve_rag_store() -> SqliteRagStore:
        nonlocal owned_rag_store
        if rag_store is not None:
            return rag_store
        if owned_rag_store is None:
            owned_rag_store = SqliteRagStore(resolved_settings.rag_db_path)
        return owned_rag_store

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

    # ----- Jobs API ---------------------------------------------------------

    @app.get("/v1/knowledge/jobs")
    async def list_jobs(
        company_type: str | None = Query(default=None),
        company: str | None = Query(default=None),
        user_id: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, list[dict[str, object]]]:
        store = resolve_rag_store()
        rows = store.list_jobs(
            company_type=company_type, company=company, user_id=user_id, limit=limit
        )
        return {"items": [_row_to_job(row) for row in rows]}

    @app.get("/v1/knowledge/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, object]:
        store = resolve_rag_store()
        row = store.get_job(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _row_to_job(row)

    # ----- Preparation metadata --------------------------------------------

    @app.get("/v1/knowledge/preparation")
    async def list_preparation(
        user_id: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, list[dict[str, object]]]:
        # MVP: no dedicated preparation table yet. Return empty list; the
        # ingestion pipeline will be added before this endpoint returns real data.
        del user_id, limit
        return {"items": []}

    # ----- Personal document metadata ---------------------------------------

    @app.get("/v1/me/documents")
    async def list_my_documents(
        user_id: str = Query(default=..., min_length=1, max_length=128),
    ) -> dict[str, list[dict[str, object]]]:
        store = resolve_rag_store()
        rows = store.list_user_documents(user_id)
        return {
            "items": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "category": row["category"],
                    "file_format": row["file_format"],
                    "size_text": row["size_text"],
                    "uploaded_at": row["uploaded_at"],
                    "status": row["status"],
                    "retrieval_enabled": bool(row["retrieval_enabled"]),
                }
                for row in rows
            ]
        }

    @app.delete("/v1/me/documents/{doc_id}")
    async def delete_my_document(
        doc_id: str,
        user_id: str = Query(default=..., min_length=1, max_length=128),
    ) -> dict[str, str]:
        store = resolve_rag_store()
        if not store.delete_user_document(doc_id, user_id):
            raise HTTPException(status_code=404, detail="document not found")
        return {"status": "ok"}

    return app


def _row_to_job(row) -> dict[str, object]:
    import json

    locations = json.loads(row["locations_json"])
    status = row["status"]
    if status == "active":
        deadline_status = "招聘中"
    elif status == "expired":
        deadline_status = "已截止"
    elif row["deadline"] is None:
        deadline_status = "时间未知"
    else:
        deadline_status = "即将截止"
    org_map = {
        "central_soe": "央企",
        "local_soe": "地方国企",
        "private": "民营企业",
        "foreign": "外资企业",
        "government": "政府部门",
        "public_institution": "事业单位",
        "unknown": "未知",
    }
    return {
        "id": row["id"],
        "company_type": org_map.get(row["organization_type"], "未知"),
        "organization_type": row["organization_type"],
        "company": row["company_name"],
        "role": row["role_title"],
        "role_family": row["role_family"],
        "recruiting_type": row["recruiting_type"],
        "locations": locations,
        "location": locations[0] if locations else "未注明",
        "posted_at": row["posted_at"],
        "deadline": row["deadline"],
        "deadline_status": deadline_status,
        "status": row["status"],
        "source": row["source_name"] or row["source_level"],
        "source_level": row["source_level"],
        "source_url": row["source_url"],
        "apply_url": row["apply_url"],
        "updated_at": row["verified_at"],
        "description": row["job_description"],
        "requirements": row["requirements"],
    }


app = create_app()
