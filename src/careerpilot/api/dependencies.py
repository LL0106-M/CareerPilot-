from collections.abc import Callable

from langchain_core.tools import BaseTool

from careerpilot.agent.model import create_qwen_model
from careerpilot.agent.runtime import CareerPilotResponder
from careerpilot.agent.service import AgentService
from careerpilot.config import Settings
from careerpilot.harness.session import SqliteSessionStore
from careerpilot.memory.cognitive_store import SqliteCognitiveStore
from careerpilot.memory.base import DisabledMemoryStore, MemoryStore
from careerpilot.memory.memos import MemosCloudMemoryStore
from careerpilot.memory.service import MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.store import SqliteRagStore
from careerpilot.rag.tool import build_agentic_rag_tool
from careerpilot.search.aliyun import AliyunWebSearchProvider
from careerpilot.support.policy import SupportPolicy


def build_agent_service(
    settings: Settings,
    action_tool_factory: Callable[[str], tuple[BaseTool, ...]] | None = None,
) -> tuple[
    AgentService,
    MemoryStore,
    SqliteRagStore,
    SqliteCognitiveStore,
    SqliteSessionStore,
    SqliteUnifiedMemoryStore,
]:
    memory_store: MemoryStore
    if settings.memos_api_key is None:
        memory_store = DisabledMemoryStore()
    else:
        memory_store = MemosCloudMemoryStore(
            settings.memos_api_key.get_secret_value(),
            base_url=settings.memos_base_url,
        )
    rag_store = SqliteRagStore(
        settings.rag_db_path,
        embedder=create_embedding_provider(settings),
    )
    cognitive_store = SqliteCognitiveStore(settings.memory_db_path)
    unified_store = SqliteUnifiedMemoryStore(settings.memory_db_path)
    unified_memory_service = MemoryService(unified_store)
    session_store = SqliteSessionStore(settings.session_db_path)
    model = create_qwen_model(settings)
    provider = build_search_provider(settings)
    agent = CareerPilotResponder(model, session_store=session_store)
    return (
        AgentService(
            memory_store,
            agent,
            SupportPolicy(),
            rag_tool_factory=lambda user_id: build_agentic_rag_tool(
                rag_store, provider, user_id=user_id
            ),
            action_tool_factory=action_tool_factory,
            cognitive_store=cognitive_store,
            unified_memory_service=unified_memory_service,
        ),
        memory_store,
        rag_store,
        cognitive_store,
        session_store,
        unified_store,
    )


def build_agent_tools(settings: Settings, rag_store: SqliteRagStore) -> list:
    return [build_agentic_rag_tool(rag_store, build_search_provider(settings))]


def build_search_provider(settings: Settings) -> AliyunWebSearchProvider | None:
    if settings.search_configured:
        assert settings.dashscope_api_key is not None
        assert settings.dashscope_base_url is not None
        return AliyunWebSearchProvider(
            api_key=settings.dashscope_api_key.get_secret_value(),
            base_url=settings.dashscope_base_url,
            model=settings.search_model,
            timeout_seconds=settings.search_timeout_seconds,
        )
    return None
