from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

import httpx
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.service import ActionService, ConfirmationError, GrantRequiredError
from careerpilot.actions.store import SqliteActionStore
from careerpilot.actions.tool import build_action_tools
from careerpilot.agent.service import ChatCommand, ChatResult
from careerpilot.api.auth import (
    COOKIE_NAME,
    Identity,
    generate_conversation_id,
    read_or_create_identity,
)
from careerpilot.api.dependencies import build_agent_service, build_search_provider
from careerpilot.api.schemas import (
    ActionApplyRequest,
    ActionConfirmRequest,
    ActionPreviewRequest,
    ChatRequest,
    ChatResponse,
    HypothesisDecisionRequest,
    IntegrationGrantRequest,
    JourneyUpdateRequest,
    RagQueryRequest,
)
from careerpilot.config import Settings, get_settings
from careerpilot.connectors.feishu_cli import FeishuCliConnector
from careerpilot.connectors.netease_mail import NeteaseMailConnector
from careerpilot.connectors.wps import WpsConnector
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.memos import MemosCloudMemoryStore
from careerpilot.product_store import ProductStore
from careerpilot.rag.agentic import AgenticRagOrchestrator, AgenticRetrievalRequest
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.routing import KnowledgeScope
from careerpilot.rag.store import SqliteRagStore


class ChatService(Protocol):
    async def chat(self, command: ChatCommand) -> ChatResult: ...


def create_app(
    settings: Settings | None = None,
    chat_service: ChatService | None = None,
    rag_store: SqliteRagStore | None = None,
    action_store: SqliteActionStore | None = None,
    action_service: ActionService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    owned_memory_store: MemosCloudMemoryStore | None = None
    owned_rag_store: SqliteRagStore | None = None
    owned_cognitive_store: SqliteCognitiveStore | None = None
    owned_product_store: ProductStore | None = None
    owned_action_store: SqliteActionStore | None = None
    owned_http_clients: list[httpx.AsyncClient] = []
    action_registry = build_mvp_capability_registry()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_memory_store is not None:
            await owned_memory_store.aclose()
        if owned_rag_store is not None:
            owned_rag_store.close()
        if owned_cognitive_store is not None:
            owned_cognitive_store.close()
        if owned_product_store is not None:
            owned_product_store.close()
        if owned_action_store is not None:
            owned_action_store.close()
        for client in owned_http_clients:
            await client.aclose()

    app = FastAPI(title="CareerPilot Agent API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    def resolve_identity(
        response: Response,
        careerpilot_owner: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> Identity:
        return read_or_create_identity(
            response,
            careerpilot_owner,
            secret=resolved_settings.cookie_secret.get_secret_value(),
            secure_cookie=resolved_settings.secure_cookies,
            accept_unsigned=resolved_settings.environment != "production",
        )

    def resolve_chat_service() -> ChatService:
        nonlocal chat_service, owned_memory_store, owned_rag_store, owned_cognitive_store
        if chat_service is None:
            try:
                (
                    chat_service,
                    owned_memory_store,
                    owned_rag_store,
                    owned_cognitive_store,
                ) = build_agent_service(
                    resolved_settings,
                    action_tool_factory=lambda owner_id: build_action_tools(
                        owner_id,
                        action_registry,
                        resolve_action_store(),
                        resolve_action_service(),
                    ),
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return chat_service

    def resolve_rag_store() -> SqliteRagStore:
        nonlocal owned_rag_store
        if rag_store is not None:
            return rag_store
        if owned_rag_store is None:
            owned_rag_store = SqliteRagStore(
                resolved_settings.rag_db_path,
                embedder=create_embedding_provider(resolved_settings),
            )
        return owned_rag_store

    def resolve_product_store() -> ProductStore:
        nonlocal owned_product_store
        if owned_product_store is None:
            owned_product_store = ProductStore(resolved_settings.product_db_path)
        return owned_product_store

    def resolve_action_store() -> SqliteActionStore:
        nonlocal owned_action_store
        if action_store is not None:
            return action_store
        if owned_action_store is None:
            owned_action_store = SqliteActionStore(resolved_settings.action_db_path)
        return owned_action_store

    def resolve_action_service() -> ActionService:
        nonlocal action_service
        if action_service is not None:
            return action_service
        connectors = {
            "feishu": FeishuCliConnector(
                executable=resolved_settings.feishu_cli_executable,
                timeout_seconds=resolved_settings.feishu_cli_timeout_seconds,
            )
        }
        if (
            resolved_settings.wps_access_token is not None
            and resolved_settings.wps_drive_id
            and resolved_settings.wps_parent_id
        ):
            client = httpx.AsyncClient(base_url=resolved_settings.wps_base_url)
            owned_http_clients.append(client)
            connectors["wps"] = WpsConnector(
                client=client,
                access_token=resolved_settings.wps_access_token.get_secret_value(),
                drive_id=resolved_settings.wps_drive_id,
                parent_id=resolved_settings.wps_parent_id,
            )
        if (
            resolved_settings.netease_account
            and resolved_settings.netease_authorization_code is not None
        ):
            connectors["netease_mail"] = NeteaseMailConnector(
                host=resolved_settings.netease_imap_host,
                port=resolved_settings.netease_imap_port,
                account=resolved_settings.netease_account,
                authorization_code=(
                    resolved_settings.netease_authorization_code.get_secret_value()
                ),
            )
        action_service = ActionService(
            registry=action_registry,
            store=resolve_action_store(),
            connectors=connectors,
        )
        return action_service

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": resolved_settings.app_name}

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> ChatResponse:
        """Chat endpoint. ``owner_id`` is derived from an HttpOnly cookie —
        the client request body can never override it.
        """
        service = resolve_chat_service()
        conversation_id = request.conversation_id or generate_conversation_id()
        result = await service.chat(
            ChatCommand(
                user_id=identity.owner_id,
                conversation_id=conversation_id,
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

    @app.post("/v1/rag/query")
    async def query_rag(
        request: RagQueryRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        """Standalone RAG boundary with external and internal query routing."""
        orchestrator = AgenticRagOrchestrator(
            resolve_rag_store(),
            web_search=build_search_provider(resolved_settings),
        )
        result = await orchestrator.retrieve(
            AgenticRetrievalRequest(
                query=request.query,
                scopes=tuple(KnowledgeScope(scope) for scope in request.scopes or ()),
                user_id=identity.owner_id,
                sub_queries=tuple(request.sub_queries),
                requires_freshness=request.requires_freshness,
                minimum_sources=request.minimum_sources,
                limit=request.limit,
            )
        )
        return {
            "status": result.status,
            "scopes": [scope.value for scope in result.trace.scopes],
            "needs_online_search": result.needs_online_search,
            "needs_ingestion": result.needs_ingestion,
            "route": {
                "external_reason": result.trace.external_route_reason,
                "internal": list(result.trace.internal_routes),
                "retrieval_mode": result.trace.retrieval_mode.value,
                "graph_mode": result.trace.graph_mode.value,
            },
            "query_analysis": {
                "normalized_query": result.query_analysis.normalized_query,
                "intent": result.query_analysis.intent.value,
                "requires_freshness": result.query_analysis.requires_freshness,
                "entities": result.query_analysis.entities,
                "sub_queries": list(result.query_analysis.sub_queries),
            },
            "retrieval": {
                "local_rounds": result.trace.local_rounds,
                "online_rounds": result.trace.online_rounds,
                "used_online_search": result.trace.used_online_search,
                "stop_reason": result.trace.stop_reason,
            },
            "context_pack": result.context_pack.to_dict(),
            "context_for_model": result.context_pack.render_for_model(),
        }

    @app.get("/v1/rag/health")
    async def rag_health() -> dict[str, object]:
        return resolve_rag_store().index_health()

    # ----- Jobs (public, owner_id = None) ----------------------------------

    @app.get("/v1/knowledge/jobs")
    async def list_jobs(
        company_type: str | None = Query(default=None),
        company: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, list[dict[str, object]]]:
        store = resolve_rag_store()
        # Jobs are curated knowledge, not user-owned. owner_id=None
        # matches the RAG ingestion contract.
        rows = store.list_jobs(
            company_type=company_type, company=company, user_id=None, limit=limit
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
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, list[dict[str, object]]]:
        del limit
        return {"items": []}

    # ----- Personal documents (user-owned) --------------------------------

    @app.get("/v1/me/documents")
    async def list_my_documents(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, list[dict[str, object]]]:
        store = resolve_rag_store()
        rows = store.list_user_documents(identity.owner_id)
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
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        store = resolve_rag_store()
        if not store.delete_user_document(doc_id, identity.owner_id):
            raise HTTPException(status_code=404, detail="document not found")
        return {"status": "ok"}

    # ----- Owner-scoped product state -------------------------------------

    @app.get("/v1/me/dashboard")
    async def get_dashboard(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        return resolve_product_store().dashboard(identity.owner_id)

    @app.post("/v1/me/hypotheses/{hypothesis_id}/decision")
    async def decide_hypothesis(
        hypothesis_id: str,
        body: HypothesisDecisionRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        if not resolve_product_store().decide_hypothesis(
            identity.owner_id, hypothesis_id, body.decision
        ):
            raise HTTPException(status_code=404, detail="hypothesis not found")
        return {"status": "ok"}

    @app.post("/v1/me/hypotheses/{hypothesis_id}/verification-task")
    async def create_verification_task(
        hypothesis_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        task = resolve_product_store().create_verification_task(
            identity.owner_id, hypothesis_id
        )
        if task is None:
            raise HTTPException(status_code=404, detail="hypothesis not found")
        return task

    @app.patch("/v1/me/journey/{task_id}")
    async def update_journey_task(
        task_id: str,
        body: JourneyUpdateRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        if not resolve_product_store().update_task(
            identity.owner_id, task_id, body.state, body.reflection
        ):
            raise HTTPException(status_code=404, detail="task not found")
        return {"status": "ok"}

    # ----- Governed external integrations and actions --------------------

    @app.get("/v1/me/integrations")
    async def list_integrations(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        states = resolve_action_store().list_authorization(identity.owner_id, action_registry)
        return {
            "items": [
                {
                    "provider_id": state.provider_id,
                    "capability": state.capability,
                    "grant_state": state.grant_state,
                    "grant_id": state.grant_id,
                    "scope_snapshot": list(state.scope_snapshot),
                    "risk_level": action_registry.get(
                        state.provider_id, state.capability
                    ).risk_level,
                    "requires_confirmation": action_registry.get(
                        state.provider_id, state.capability
                    ).requires_confirmation,
                }
                for state in states
            ]
        }

    @app.post("/v1/me/integrations/{provider_id}/grants", status_code=201)
    async def grant_integration(
        provider_id: str,
        body: IntegrationGrantRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            for capability in body.capabilities:
                action_registry.get(provider_id, capability)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        grant = resolve_action_store().grant(
            owner_id=identity.owner_id,
            provider_id=provider_id,
            capabilities=body.capabilities,
            purpose=body.purpose,
            scope_snapshot=body.scope_snapshot,
            resource_constraints=body.resource_constraints,
        )
        return {
            "grant_id": grant.id,
            "provider_id": grant.provider_id,
            "capabilities": list(grant.capabilities),
            "purpose": grant.purpose,
            "scope_snapshot": list(grant.scope_snapshot),
        }

    @app.delete("/v1/me/integrations/{provider_id}/grants/{grant_id}")
    async def revoke_integration(
        provider_id: str,
        grant_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        del provider_id
        if not resolve_action_store().revoke(identity.owner_id, grant_id):
            raise HTTPException(status_code=404, detail="grant not found")
        return {"status": "revoked"}

    @app.post("/v1/me/actions/preview", status_code=201)
    async def preview_action(
        body: ActionPreviewRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            preview = resolve_action_service().preview(
                identity.owner_id, body.provider_id, body.capability, body.payload
            )
            definition = action_registry.get(body.provider_id, body.capability)
        except GrantRequiredError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "action_id": preview.id,
            "provider_id": preview.provider_id,
            "capability": preview.capability,
            "payload": preview.payload,
            "preview_hash": preview.preview_hash,
            "requires_confirmation": definition.requires_confirmation,
        }

    @app.post("/v1/me/actions/{action_id}/confirm", status_code=201)
    async def confirm_action(
        action_id: str,
        body: ActionConfirmRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        try:
            confirmation = resolve_action_service().confirm(
                identity.owner_id, action_id, body.preview_hash
            )
        except GrantRequiredError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ConfirmationError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "action_id": action_id,
            "confirmation_token": confirmation.token,
            "preview_hash": confirmation.preview_hash,
        }

    @app.post("/v1/me/actions/{action_id}/apply")
    async def apply_action(
        action_id: str,
        body: ActionApplyRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            receipt = await resolve_action_service().apply(
                identity.owner_id,
                action_id,
                body.confirmation_token,
                body.preview_hash,
                body.idempotency_key,
            )
        except GrantRequiredError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ConfirmationError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=503, detail="connector is not configured") from error
        return {
            "receipt_id": receipt.id,
            "action_id": receipt.action_id,
            "provider_id": receipt.provider_id,
            "status": receipt.status,
            "external_reference": receipt.external_reference,
            "observations": list(receipt.observations),
            "retryable": receipt.retryable,
        }

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
