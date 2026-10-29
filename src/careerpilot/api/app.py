import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Protocol
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.gzip import GZipMiddleware

from careerpilot.actions.payloads import validate_grant_constraints
from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.service import (
    ActionService,
    ConfirmationError,
    GrantRequiredError,
    IdempotencyConflictError,
    PayloadValidationError,
    ResourceConstraintError,
)
from careerpilot.actions.store import SqliteActionStore
from careerpilot.actions.tool import build_action_tools
from careerpilot.agent.model import create_reasoning_model
from careerpilot.agent.service import ChatCommand, ChatResult, ChatStreamEvent
from careerpilot.api.auth import (
    SESSION_COOKIE_NAME,
    Identity,
    generate_conversation_id,
)
from careerpilot.api.dependencies import build_agent_service, build_search_provider
from careerpilot.api.schemas import (
    ActionApplyRequest,
    ActionConfirmRequest,
    ActionPreviewRequest,
    AgentRunResponse,
    ChatRequest,
    ChatResponse,
    HypothesisDecisionRequest,
    IdeaActionLinkRequest,
    IdeaCreateRequest,
    IdeaStageRequest,
    IdeaUpdateRequest,
    IntegrationGrantRequest,
    JourneyUpdateRequest,
    LoginRequest,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    RagQueryRequest,
    RegisterRequest,
    RunEventResponse,
    RunEventsResponse,
    VerificationCodeRequest,
    VersionRequest,
)
from careerpilot.api.static import SPAStaticFiles
from careerpilot.auth.mailer import SmtpVerificationMailer
from careerpilot.auth.passwords import PasswordHasher
from careerpilot.auth.service import AuthenticationError, AuthService, LoginRateLimitError
from careerpilot.auth.store import DuplicateAccountError, SqliteAuthStore
from careerpilot.auth.verification import (
    InvalidVerificationCodeError,
    VerificationDeliveryError,
    VerificationRateLimitError,
    VerificationService,
)
from careerpilot.config import Settings, get_settings
from careerpilot.connectors.feishu_cli import FeishuCliConnector
from careerpilot.connectors.netease_mail import NeteaseMailConnector
from careerpilot.connectors.wps import WpsConnector
from careerpilot.harness.run_store import SqliteAgentRunStore
from careerpilot.harness.runtime import RunCancellationRequested
from careerpilot.harness.session import SqliteSessionStore
from careerpilot.memory.base import MemoryStore
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.daily_review import DailyReview
from careerpilot.memory.dreaming_llm import JsonDreamingAnalyzer
from careerpilot.memory.ideas import IdeaItem, IdeaService, IdeaStorageDeniedError
from careerpilot.memory.manual_dreaming import (
    ManualDreamingNoEvidence,
    ManualDreamingService,
    collect_recent_evidence,
)
from careerpilot.memory.models import MemoryRecord, MemoryStatus, MemoryType
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import (
    MemoryNotFoundError,
    MemoryVersionConflictError,
    SqliteUnifiedMemoryStore,
)
from careerpilot.product_store import ProductStore
from careerpilot.rag.agentic import AgenticRagOrchestrator, AgenticRetrievalRequest
from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.loaders import load_document
from careerpilot.rag.models import KnowledgeOrigin
from careerpilot.rag.routing import KnowledgeScope
from careerpilot.rag.store import SqliteRagStore


class ChatService(Protocol):
    async def chat(self, command: ChatCommand) -> ChatResult: ...

    def stream_chat(self, command: ChatCommand) -> AsyncIterator[ChatStreamEvent]: ...


def _request_origin_is_allowed(
    request: Request, origin: str, configured_origins: list[str]
) -> bool:
    normalized = origin.rstrip("/")
    if normalized in {item.rstrip("/") for item in configured_origins}:
        return True
    parsed = urlsplit(normalized)
    forwarded_host = request.headers.get("x-forwarded-host")
    effective_host = (forwarded_host or request.headers.get("host") or "").split(",", 1)[0].strip()
    forwarded_proto = request.headers.get("x-forwarded-proto")
    effective_proto = (forwarded_proto or request.url.scheme).split(",", 1)[0].strip()
    return bool(
        parsed.scheme
        and parsed.netloc
        and parsed.scheme.casefold() == effective_proto.casefold()
        and parsed.netloc.casefold() == effective_host.casefold()
    )


def create_app(
    settings: Settings | None = None,
    chat_service: ChatService | None = None,
    rag_store: SqliteRagStore | None = None,
    action_store: SqliteActionStore | None = None,
    action_service: ActionService | None = None,
    memory_service: MemoryService | None = None,
    idea_service: IdeaService | None = None,
    cognitive_store: SqliteCognitiveStore | None = None,
    product_store: ProductStore | None = None,
    run_store: SqliteAgentRunStore | None = None,
    auth_service: AuthService | None = None,
    manual_dreaming_service: ManualDreamingService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    owned_memory_store: MemoryStore | None = None
    owned_rag_store: SqliteRagStore | None = None
    owned_cognitive_store: SqliteCognitiveStore | None = None
    owned_session_store: SqliteSessionStore | None = None
    owned_product_store: ProductStore | None = None
    owned_action_store: SqliteActionStore | None = None
    owned_unified_memory_store: SqliteUnifiedMemoryStore | None = None
    owned_run_store: SqliteAgentRunStore | None = None
    owned_http_clients: list[httpx.AsyncClient] = []
    action_registry = build_mvp_capability_registry()

    class UnavailableMailer:
        def send_registration_code(self, recipient: str, code: str) -> None:
            del recipient, code
            raise RuntimeError("SMTP is not configured")

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
        if owned_product_store is not None:
            owned_product_store.close()
        if owned_action_store is not None:
            owned_action_store.close()
        if owned_unified_memory_store is not None:
            owned_unified_memory_store.close()
        if owned_run_store is not None:
            owned_run_store.close()
        for client in owned_http_clients:
            await client.aclose()

    app = FastAPI(title="CareerPilot Agent API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    @app.middleware("http")
    async def reject_cross_site_cookie_mutations(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get(
            SESSION_COOKIE_NAME
        ):
            origin = request.headers.get("origin")
            if origin is not None and not _request_origin_is_allowed(
                request, origin, resolved_settings.allowed_origins
            ):
                return JSONResponse(
                    status_code=403, content={"detail": "cross-site request denied"}
                )
        return await call_next(request)

    def resolve_auth_service() -> AuthService:
        nonlocal auth_service
        if auth_service is None:
            store = SqliteAuthStore(resolved_settings.auth_db_path)
            if (
                resolved_settings.smtp_account is not None
                and resolved_settings.smtp_authorization_code is not None
            ):
                mailer = SmtpVerificationMailer(
                    host=resolved_settings.smtp_host,
                    port=resolved_settings.smtp_port,
                    account=resolved_settings.smtp_account,
                    authorization_code=resolved_settings.smtp_authorization_code.get_secret_value(),
                    sender_name=resolved_settings.smtp_sender_name,
                )
            else:
                mailer = UnavailableMailer()
            verification = VerificationService(
                store=store,
                mailer=mailer,
                secret=resolved_settings.cookie_secret.get_secret_value(),
            )
            auth_service = AuthService(
                store=store,
                password_hasher=PasswordHasher(),
                verification=verification,
            )
        return auth_service

    def resolve_identity(
        response: Response,
        session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> Identity:
        account = resolve_auth_service().authenticate(session_cookie)
        if account is None:
            response.delete_cookie(SESSION_COOKIE_NAME, path="/")
            raise HTTPException(
                status_code=401,
                detail="authentication required",
                headers={
                    "Set-Cookie": (
                        f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=lax"
                    )
                },
            )
        if session_cookie is not None and resolve_auth_service().is_remembered_session(
            session_cookie
        ):
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_cookie,
                max_age=5 * 24 * 60 * 60,
                httponly=True,
                secure=resolved_settings.secure_cookies,
                samesite="lax",
                path="/",
            )
        return Identity(owner_id=account.id, is_anonymous=False)

    def resolve_chat_service() -> ChatService:
        nonlocal chat_service, owned_memory_store, owned_rag_store
        nonlocal owned_cognitive_store, owned_session_store, owned_unified_memory_store
        nonlocal owned_run_store
        if chat_service is None:
            try:
                (
                    chat_service,
                    owned_memory_store,
                    owned_rag_store,
                    owned_cognitive_store,
                    owned_session_store,
                    owned_unified_memory_store,
                    owned_run_store,
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

    def resolve_run_store() -> SqliteAgentRunStore:
        nonlocal run_store, owned_run_store
        if run_store is not None:
            return run_store
        if owned_run_store is None:
            owned_run_store = SqliteAgentRunStore(resolved_settings.session_db_path)
        return owned_run_store

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
        if product_store is not None:
            return product_store
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
                access_key=(
                    resolved_settings.wps_access_key.get_secret_value()
                    if resolved_settings.wps_access_key is not None
                    else None
                ),
                secret_key=(
                    resolved_settings.wps_secret_key.get_secret_value()
                    if resolved_settings.wps_secret_key is not None
                    else None
                ),
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

    def resolve_memory_service() -> MemoryService:
        nonlocal memory_service, owned_unified_memory_store
        if memory_service is None:
            owned_unified_memory_store = SqliteUnifiedMemoryStore(resolved_settings.memory_db_path)
            memory_service = MemoryService(
                owned_unified_memory_store,
                embedder=create_embedding_provider(resolved_settings),
            )
        return memory_service

    def resolve_idea_service() -> IdeaService:
        nonlocal idea_service
        if idea_service is None:
            idea_service = IdeaService(resolve_memory_service())
        return idea_service

    def resolve_cognitive_store() -> SqliteCognitiveStore:
        nonlocal cognitive_store, owned_cognitive_store
        if cognitive_store is not None:
            return cognitive_store
        if owned_cognitive_store is None:
            owned_cognitive_store = SqliteCognitiveStore(resolved_settings.memory_db_path)
        return owned_cognitive_store

    def resolve_manual_dreaming_service() -> ManualDreamingService:
        nonlocal manual_dreaming_service
        if manual_dreaming_service is None:
            manual_dreaming_service = ManualDreamingService(
                resolve_cognitive_store(),
                JsonDreamingAnalyzer(create_reasoning_model(resolved_settings)),
                resolve_memory_service(),
                lambda owner_id, local_day: collect_recent_evidence(
                    owner_id,
                    local_day,
                    resolve_memory_service(),
                    resolve_product_store(),
                    resolve_rag_store(),
                ),
            )
        return manual_dreaming_service

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": resolved_settings.app_name}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        try:
            for database_path in resolved_settings.runtime_database_paths:
                database_path.parent.mkdir(parents=True, exist_ok=True)
            if (
                resolved_settings.frontend_dist_path is not None
                and not (resolved_settings.frontend_dist_path / "index.html").is_file()
            ):
                raise OSError("frontend bundle is missing")
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"service is not ready: {exc}") from exc
        return {"status": "ready", "service": resolved_settings.app_name}

    def account_payload(account) -> dict[str, str]:
        return {"id": account.id, "username": account.username, "email": account.email}

    @app.post("/v1/auth/verification-codes", status_code=202)
    async def request_verification_code(
        body: VerificationCodeRequest, request: Request
    ) -> dict[str, object]:
        source = request.client.host if request.client is not None else "unknown"
        source_key = hashlib.sha256(source.encode()).hexdigest()
        try:
            dispatch = resolve_auth_service().request_registration_code(body.email, source_key)
        except DuplicateAccountError as error:
            raise HTTPException(status_code=409, detail={"field": error.field}) from error
        except VerificationRateLimitError as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        except VerificationDeliveryError as error:
            raise HTTPException(status_code=503, detail="验证码邮件暂时无法发送") from error
        return {
            "status": "sent",
            "expires_at": dispatch.expires_at.isoformat(),
            "retry_after_seconds": dispatch.retry_after_seconds,
        }

    @app.post("/v1/auth/register", status_code=201)
    async def register(body: RegisterRequest) -> dict[str, str]:
        try:
            account = resolve_auth_service().register(
                username=body.username,
                email=body.email,
                password=body.password,
                code=body.verification_code,
            )
        except DuplicateAccountError as error:
            raise HTTPException(status_code=409, detail={"field": error.field}) from error
        except InvalidVerificationCodeError as error:
            raise HTTPException(status_code=422, detail="验证码错误或已失效") from error
        return account_payload(account)

    @app.post("/v1/auth/login")
    async def login(body: LoginRequest, request: Request, response: Response) -> dict[str, str]:
        source = request.client.host if request.client is not None else "unknown"
        source_key = hashlib.sha256(source.encode()).hexdigest()
        try:
            result = resolve_auth_service().login(
                identifier=body.identifier,
                password=body.password,
                remember_me=body.remember_me,
                source_key=source_key,
            )
        except LoginRateLimitError as error:
            raise HTTPException(status_code=429, detail="登录尝试过多，请稍后再试") from error
        except AuthenticationError as error:
            raise HTTPException(status_code=401, detail="用户名、邮箱或密码不正确") from error
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=result.cookie_value,
            max_age=5 * 24 * 60 * 60 if result.remember_me else None,
            httponly=True,
            secure=resolved_settings.secure_cookies,
            samesite="lax",
            path="/",
        )
        return account_payload(result.account)

    @app.get("/v1/auth/me")
    async def current_account(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        account = resolve_auth_service().store.get_account(identity.owner_id)
        if account is None:
            raise HTTPException(status_code=401, detail="authentication required")
        return account_payload(account)

    @app.post("/v1/auth/logout")
    async def logout(
        response: Response,
        session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> dict[str, str]:
        resolve_auth_service().logout(session_cookie)
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return {"status": "ok"}

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
        try:
            result = await service.chat(
                ChatCommand(
                    user_id=identity.owner_id,
                    conversation_id=conversation_id,
                    message=request.message,
                    requested_mode=request.support_mode,
                )
            )
        except RunCancellationRequested as exc:
            raise HTTPException(status_code=409, detail="run cancelled") from exc
        resolve_product_store().record_conversation_turn(
            identity.owner_id,
            result.conversation_id,
            request.message,
            result.reply,
        )
        return _chat_response(result)

    @app.post("/v1/chat/stream")
    async def stream_chat(
        body: ChatRequest,
        http_request: Request,
        identity: Identity = Depends(resolve_identity),
    ) -> StreamingResponse:
        conversation_id = body.conversation_id or generate_conversation_id()
        command = ChatCommand(
            user_id=identity.owner_id,
            conversation_id=conversation_id,
            message=body.message,
            requested_mode=body.support_mode,
        )

        async def events() -> AsyncIterator[str]:
            try:
                async for event in resolve_chat_service().stream_chat(command):
                    if await http_request.is_disconnected():
                        return
                    if event.type == "delta":
                        yield _sse_event("delta", {"text": event.text})
                    elif event.result is not None:
                        result = event.result
                        resolve_product_store().record_conversation_turn(
                            identity.owner_id,
                            result.conversation_id,
                            body.message,
                            result.reply,
                        )
                        payload = _chat_response(result).model_dump(mode="json")
                        yield _sse_event("completed", payload)
            except RunCancellationRequested:
                yield _sse_event("error", {"message": "run cancelled"})
            except Exception:
                yield _sse_event("error", {"message": "这次没有送达，请稍后再试。"})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/v1/me/conversations")
    async def list_my_conversations(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, list[dict[str, object]]]:
        return {"items": resolve_product_store().list_conversations(identity.owner_id)}

    @app.get("/v1/me/conversations/{conversation_id}")
    async def get_my_conversation(
        conversation_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        conversation = resolve_product_store().get_conversation(identity.owner_id, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return conversation

    @app.get("/v1/runs/{run_id}", response_model=AgentRunResponse)
    async def get_agent_run(
        run_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> AgentRunResponse:
        record = await resolve_run_store().get(identity.owner_id, run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        return AgentRunResponse(
            run_id=record.run_id,
            conversation_id=record.conversation_id,
            status=record.status,
            stage=record.stage.value,
            runtime_phase=record.runtime_phase,
            step=record.step,
            version=record.version,
            cancellation_requested=record.cancellation_requested,
            result=record.result_json,
            error=record.error_json,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @app.get("/v1/runs/{run_id}/events", response_model=RunEventsResponse)
    async def get_agent_run_events(
        run_id: str,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=200, ge=1, le=500),
        identity: Identity = Depends(resolve_identity),
    ) -> RunEventsResponse:
        events = await resolve_run_store().list_events(
            identity.owner_id, run_id, after=after, limit=limit
        )
        if events is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunEventsResponse(
            items=tuple(
                RunEventResponse(
                    sequence=item.sequence,
                    event_type=item.event_type,
                    stage=item.stage,
                    runtime_phase=item.runtime_phase,
                    step=item.step,
                    data=item.data,
                    created_at=item.created_at,
                )
                for item in events
            )
        )

    @app.post("/v1/runs/{run_id}/cancel")
    async def cancel_agent_run(
        run_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        record = await resolve_run_store().get(identity.owner_id, run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="run not found")
        if record.status != "running":
            raise HTTPException(status_code=409, detail="run is already terminal")
        await resolve_run_store().request_cancel(identity.owner_id, run_id)
        return {"status": "cancellation_requested"}

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
            "evidence_assessment": {
                "status": result.assessment.status,
                "relevant_evidence_count": result.assessment.relevant_evidence_count,
                "distinct_sources": result.assessment.distinct_sources,
                "minimum_sources": result.assessment.minimum_sources,
                "missing_reasons": list(result.assessment.missing_reasons),
            },
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
        rows = resolve_rag_store().list_documents_for_domains(
            ("preparation_material", "curated_document", "domain_knowledge", "ai_frontier"),
            limit=limit,
        )
        items: list[dict[str, object]] = []
        for row in rows:
            metadata = json.loads(str(row["metadata_json"] or "{}"))
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "publisher": (
                        metadata.get("publisher") or metadata.get("site_name") or "来源网页"
                    ),
                    "category": metadata.get("category") or "其他",
                    "format": metadata.get("format") or "网页",
                    "url": row["source_uri"],
                    "description": str(row["text"] or "")[:500],
                    "updated_at": row["fetched_at"] or row["published_at"] or "",
                    "source_type": row["source_type"],
                }
            )
        return {"items": items}

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
        store.delete_owned_document(doc_id, identity.owner_id)
        upload_dir = resolved_settings.rag_db_path.parent / "uploads" / identity.owner_id
        upload_paths = upload_dir.glob(f"{doc_id}.*") if upload_dir.exists() else ()
        for upload_path in upload_paths:
            if upload_path.is_file():
                upload_path.unlink()
        return {"status": "ok"}

    # ----- Unified memory, ideas, and daily reviews ----------------------

    @app.get("/v1/me/memories")
    async def list_memories(
        memory_type: MemoryType | None = Query(default=None, alias="type"),
        status: MemoryStatus | None = Query(default=None),
        query: str | None = Query(default=None, max_length=500),
        limit: int = Query(default=100, ge=1, le=200),
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        records = resolve_memory_service().list(
            identity.owner_id,
            statuses=(status,) if status else None,
            types=(memory_type,) if memory_type else None,
            query=query,
            limit=limit,
        )
        return {"items": [_memory_payload(item) for item in records]}

    @app.post("/v1/me/memories", status_code=201)
    async def create_memory(
        body: MemoryCreateRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        record = resolve_memory_service().create_explicit(
            owner_id=identity.owner_id,
            memory_type=body.type,
            content=body.content,
            sensitivity=body.sensitivity,
            importance=body.importance,
        )
        return _memory_payload(record)

    @app.get("/v1/me/memories/{memory_id}")
    async def get_memory(
        memory_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            return _memory_payload(resolve_memory_service().get(identity.owner_id, memory_id))
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="memory not found") from error

    @app.patch("/v1/me/memories/{memory_id}")
    async def update_memory(
        memory_id: str,
        body: MemoryUpdateRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        changes = body.model_dump(exclude={"expected_version"}, exclude_none=True)
        try:
            record = resolve_memory_service().update(
                identity.owner_id,
                memory_id,
                expected_version=body.expected_version,
                **changes,
            )
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="memory not found") from error
        except MemoryVersionConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _memory_payload(record)

    async def transition_memory(
        memory_id: str,
        body: VersionRequest,
        identity: Identity,
        operation: str,
    ) -> dict[str, object]:
        try:
            method = getattr(resolve_memory_service(), operation)
            record = method(identity.owner_id, memory_id, expected_version=body.expected_version)
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="memory not found") from error
        except (MemoryVersionConflictError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _memory_payload(record)

    @app.post("/v1/me/memories/{memory_id}/confirm")
    async def confirm_memory(
        memory_id: str,
        body: VersionRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        return await transition_memory(memory_id, body, identity, "confirm")

    @app.post("/v1/me/memories/{memory_id}/pause")
    async def pause_memory(
        memory_id: str,
        body: VersionRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        return await transition_memory(memory_id, body, identity, "pause")

    @app.post("/v1/me/memories/{memory_id}/resume")
    async def resume_memory(
        memory_id: str,
        body: VersionRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        return await transition_memory(memory_id, body, identity, "resume")

    @app.delete("/v1/me/memories/{memory_id}")
    async def delete_memory(
        memory_id: str,
        expected_version: int = Query(ge=1),
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        return await transition_memory(
            memory_id, VersionRequest(expected_version=expected_version), identity, "delete"
        )

    @app.get("/v1/me/memory-candidates")
    async def list_memory_candidates(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        records = resolve_memory_service().list(
            identity.owner_id, statuses=(MemoryStatus.CANDIDATE,)
        )
        return {"items": [_memory_payload(item) for item in records]}

    @app.get("/v1/me/ideas")
    async def list_ideas(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        return {
            "items": [
                _idea_payload(item, resolve_memory_service())
                for item in resolve_idea_service().list(identity.owner_id)
            ]
        }

    @app.post("/v1/me/documents", status_code=201)
    async def upload_my_document(
        request: Request,
        title: str = Query(min_length=1, max_length=240),
        category: str = Query(pattern="^(简历|项目与作品集|其他资料)$"),
        file_format: str = Query(pattern="^(PDF|DOCX|TXT|MD)$"),
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        content = await request.body()
        if not content:
            raise HTTPException(status_code=422, detail="file is empty")
        if len(content) > resolved_settings.max_upload_bytes:
            limit_mb = resolved_settings.max_upload_bytes / (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"file exceeds {limit_mb:g} MB")

        document_id = f"doc-{uuid4().hex[:16]}"
        extension = file_format.casefold()
        upload_dir = resolved_settings.rag_db_path.parent / "uploads" / identity.owner_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_path = upload_dir / f"{document_id}.{extension}"
        upload_path.write_bytes(content)

        payload = {
            "id": document_id,
            "title": title,
            "category": category,
            "file_format": file_format,
            "size_text": _format_file_size(len(content)),
            "uploaded_at": datetime.now(UTC).isoformat(),
            "status": "解析中",
            "retrieval_enabled": False,
            "owner_user_id": identity.owner_id,
        }
        store = resolve_rag_store()
        try:
            loaded = load_document(
                upload_path,
                domain="personal_material",
                source_type="user_upload",
                knowledge_origin=KnowledgeOrigin.USER_PROVIDED,
                owner_user_id=identity.owner_id,
                asset_dir=upload_dir / "assets",
            )
            document = replace(
                loaded,
                id=document_id,
                title=title,
                source_uri=upload_path.resolve().as_uri(),
                metadata={
                    **loaded.metadata,
                    "category": category,
                    "file_format": file_format,
                },
            )
            if not document.text.strip():
                raise ValueError("document contains no extractable text")
            store.upsert(document, chunk_document(document))
            payload["status"] = "可检索"
            payload["retrieval_enabled"] = True
        except Exception:
            payload["status"] = "解析失败"
            payload["retrieval_enabled"] = False
        store.upsert_user_document(payload)
        return {key: value for key, value in payload.items() if key != "owner_user_id"}

    @app.post("/v1/me/ideas", status_code=201)
    async def create_idea(
        body: IdeaCreateRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            item = resolve_idea_service().capture_explicit(
                owner_id=identity.owner_id,
                raw_text=body.raw_text,
                title=body.title,
                authorization=body.authorization,
                sensitivity=body.sensitivity,
                related_goal_memory_id=body.related_goal_memory_id,
            )
        except IdeaStorageDeniedError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="related memory not found") from error
        return _idea_payload(item, resolve_memory_service())

    @app.get("/v1/me/ideas/{idea_id}")
    async def get_idea(
        idea_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            item = resolve_idea_service().get(identity.owner_id, idea_id)
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="idea not found") from error
        return _idea_payload(item, resolve_memory_service())

    @app.patch("/v1/me/ideas/{idea_id}")
    async def update_idea(
        idea_id: str,
        body: IdeaUpdateRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            item = resolve_idea_service().set_next_step(
                identity.owner_id,
                idea_id,
                expected_version=body.expected_version,
                next_step=body.next_step,
            )
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="idea not found") from error
        except MemoryVersionConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _idea_payload(item, resolve_memory_service())

    @app.post("/v1/me/ideas/{idea_id}/stage")
    async def transition_idea(
        idea_id: str,
        body: IdeaStageRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            item = resolve_idea_service().update_stage(
                identity.owner_id,
                idea_id,
                expected_version=body.expected_version,
                stage=body.stage,
            )
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="idea not found") from error
        except (MemoryVersionConflictError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _idea_payload(item, resolve_memory_service())

    @app.post("/v1/me/ideas/{idea_id}/action-link")
    async def link_idea_action(
        idea_id: str,
        body: IdeaActionLinkRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            item = resolve_idea_service().link_action(
                identity.owner_id,
                idea_id,
                expected_version=body.expected_version,
                action_reference=body.action_reference,
            )
        except MemoryNotFoundError as error:
            raise HTTPException(status_code=404, detail="idea not found") from error
        except MemoryVersionConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _idea_payload(item, resolve_memory_service())

    @app.get("/v1/me/daily-reviews/{local_date}")
    async def get_daily_review(
        local_date: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        review = resolve_cognitive_store().get_daily_review(identity.owner_id, local_date)
        if review is None:
            raise HTTPException(status_code=404, detail="daily review not found")
        return _daily_review_payload(review)

    @app.get("/v1/me/daily-reviews")
    async def list_daily_reviews(
        limit: int = Query(default=30, ge=1, le=100),
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        return {
            "items": [
                _daily_review_payload(review)
                for review in resolve_cognitive_store().list_daily_reviews(identity.owner_id, limit)
            ]
        }

    @app.post("/v1/me/dreaming", status_code=202)
    async def start_manual_dreaming(
        background_tasks: BackgroundTasks,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        service = resolve_manual_dreaming_service()
        try:
            job = service.start(identity.owner_id, date.today())
        except ManualDreamingNoEvidence as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if job.status == "queued":
            background_tasks.add_task(service.run, identity.owner_id, job.id)
        return {"job_id": job.id, "status": job.status, "local_date": job.local_date}

    @app.get("/v1/me/dreaming/today")
    async def get_manual_dreaming_today(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        result = resolve_manual_dreaming_service().today(identity.owner_id, date.today())
        if result is None:
            raise HTTPException(status_code=404, detail="Dreaming result not found")
        return result

    @app.get("/v1/me/dreaming/jobs/{job_id}")
    async def get_manual_dreaming_job(
        job_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        status = resolve_manual_dreaming_service().status(identity.owner_id, job_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Dreaming job not found")
        return status

    @app.post("/v1/me/dreaming/results/{result_id}/hypotheses/{index}/confirm")
    async def confirm_manual_dreaming_hypothesis(
        result_id: str,
        index: int,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        try:
            memory_id = resolve_manual_dreaming_service().confirm_hypothesis(
                identity.owner_id, result_id, index
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"memory_id": memory_id, "status": "confirmed"}

    # ----- Owner-scoped product state -------------------------------------

    @app.get("/v1/me/dashboard")
    async def get_dashboard(
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        product = resolve_product_store().dashboard(identity.owner_id)
        canonical = resolve_memory_service().list(identity.owner_id, limit=200)
        product["memories"] = [
            _memory_payload(item) for item in canonical if item.type is not MemoryType.HYPOTHESIS
        ]
        product["hypotheses"] = [
            _memory_payload(item) for item in canonical if item.type is MemoryType.HYPOTHESIS
        ]
        governed_ideas = [
            _idea_payload(item, resolve_memory_service())
            for item in resolve_idea_service().list(identity.owner_id)
        ]
        governed_memory_ids = {str(item["memory_id"]) for item in governed_ideas}
        conversation_ideas = [
            {
                "id": item.id,
                "memory_id": item.id,
                "title": item.content,
                "raw_text": item.content,
                "stage": "captured",
                "created_at": item.created_at.isoformat(),
            }
            for item in canonical
            if item.type is MemoryType.IDEA and item.id not in governed_memory_ids
        ]
        product["ideas"] = [*governed_ideas, *conversation_ideas]
        product["dreaming"] = [
            _daily_review_payload(item)
            for item in resolve_cognitive_store().list_daily_reviews(identity.owner_id)
        ]
        return product

    @app.post("/v1/me/hypotheses/{hypothesis_id}/decision")
    async def decide_hypothesis(
        hypothesis_id: str,
        body: HypothesisDecisionRequest,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, str]:
        try:
            hypothesis = resolve_memory_service().get(identity.owner_id, hypothesis_id)
        except MemoryNotFoundError:
            hypothesis = None
        if hypothesis is None or hypothesis.type is not MemoryType.HYPOTHESIS:
            raise HTTPException(status_code=404, detail="hypothesis not found")
        if body.decision == "confirm" and hypothesis.status is MemoryStatus.CANDIDATE:
            resolve_memory_service().confirm(
                identity.owner_id, hypothesis_id, expected_version=hypothesis.version
            )
        return {"status": "ok"}

    @app.post("/v1/me/hypotheses/{hypothesis_id}/verification-task")
    async def create_verification_task(
        hypothesis_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            hypothesis = resolve_memory_service().get(identity.owner_id, hypothesis_id)
        except MemoryNotFoundError:
            hypothesis = None
        if hypothesis is None or hypothesis.type is not MemoryType.HYPOTHESIS:
            raise HTTPException(status_code=404, detail="hypothesis not found")
        return resolve_product_store().create_memory_verification_task(
            identity.owner_id,
            hypothesis.id,
            hypothesis.content,
            source="hypothesis",
        )

    @app.post("/v1/me/ideas/{idea_id}/verification-task")
    async def create_idea_verification_task(
        idea_id: str,
        identity: Identity = Depends(resolve_identity),
    ) -> dict[str, object]:
        try:
            idea = resolve_memory_service().get(identity.owner_id, idea_id)
        except MemoryNotFoundError:
            idea = None
        if idea is None or idea.type is not MemoryType.IDEA:
            raise HTTPException(status_code=404, detail="idea not found")
        return resolve_product_store().create_memory_verification_task(
            identity.owner_id,
            idea.id,
            idea.content,
            source="idea",
        )

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
        connection_states = {
            provider_id: await resolve_action_service().connection_state(provider_id)
            for provider_id in action_registry.provider_ids
        }
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
                    "configured": connection_states[state.provider_id][0],
                    "connection_state": connection_states[state.provider_id][1],
                    "last_used_at": resolve_action_store().last_used_at(
                        identity.owner_id, state.provider_id
                    ),
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
            validate_grant_constraints(provider_id, body.capabilities, body.resource_constraints)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
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
        if not resolve_action_store().revoke(identity.owner_id, grant_id, provider_id):
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
        except ResourceConstraintError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except PayloadValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
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
        except IdempotencyConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ResourceConstraintError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
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

    if resolved_settings.frontend_dist_path is not None:

        @app.api_route(
            "/v1/{unmatched_path:path}",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            include_in_schema=False,
        )
        async def unmatched_api(unmatched_path: str) -> None:
            del unmatched_path
            raise HTTPException(status_code=404, detail="Not Found")

        app.mount(
            "/",
            SPAStaticFiles(resolved_settings.frontend_dist_path),
            name="frontend",
        )

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


def _format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def _memory_payload(record: MemoryRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "type": record.type.value,
        "content": record.content,
        "status": record.status.value,
        "sensitivity": record.sensitivity.value,
        "origin": record.origin.value,
        "source_type": record.source_type.value,
        "source_reference": record.source_reference,
        "confidence": record.confidence.value,
        "importance": record.importance,
        "version": record.version,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
        "metadata": record.metadata,
    }


def _idea_payload(item: IdeaItem, memories: MemoryService) -> dict[str, object]:
    memory = memories.get(item.owner_id, item.memory_id)
    return {
        "id": item.id,
        "memory_id": item.memory_id,
        "title": item.title,
        "raw_text": memory.content,
        "stage": item.stage.value,
        "authorization": item.authorization.value,
        "memory_status": memory.status.value,
        "sensitivity": memory.sensitivity.value,
        "related_goal_memory_id": item.related_goal_memory_id,
        "next_step": item.next_step,
        "action_reference": item.action_reference,
        "version": item.version,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _daily_review_payload(review: DailyReview) -> dict[str, object]:
    return {
        "id": review.id,
        "local_date": review.local_date,
        "wins": list(review.wins),
        "ideas": list(review.ideas),
        "blockers": list(review.blockers),
        "open_loops": list(review.open_loops),
        "tomorrow_step": review.tomorrow_step,
        "source_event_ids": list(review.source_event_ids),
        "status": review.status,
        "version": review.version,
        "created_at": review.created_at.isoformat(),
        "updated_at": review.updated_at.isoformat(),
    }


def _chat_response(result: ChatResult) -> ChatResponse:
    return ChatResponse(
        conversation_id=result.conversation_id,
        run_id=result.run_id,
        result_status=result.result_status,
        citation_ids=result.citation_ids,
        citation_warnings=result.citation_warnings,
        reply=result.reply,
        support_mode=result.support_mode,
        primary_intent=result.primary_intent,
        retrieval_sources=result.retrieval_sources,
        memory_read_status=result.memory_read_status,
        memory_write_status=result.memory_write_status,
        dreaming_status=result.dreaming_status,
        memory_ids=result.memory_ids,
    )


def _sse_event(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


app = create_app()
