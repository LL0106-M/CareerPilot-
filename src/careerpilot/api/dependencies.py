from careerpilot.agent.deepagents_runtime import DeepAgentsResponder
from careerpilot.agent.model import create_qwen_model
from careerpilot.agent.service import AgentService
from careerpilot.config import Settings
from careerpilot.memory.memos import MemosCloudMemoryStore
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.store import SqliteRagStore
from careerpilot.rag.tool import build_rag_tool
from careerpilot.search.aliyun import AliyunWebSearchProvider
from careerpilot.search.tool import build_web_search_tool
from careerpilot.support.policy import SupportPolicy


def build_agent_service(
    settings: Settings,
) -> tuple[AgentService, MemosCloudMemoryStore, SqliteRagStore]:
    if settings.memos_api_key is None:
        raise RuntimeError("MEMOS_API_KEY is not configured")
    memory_store = MemosCloudMemoryStore(
        settings.memos_api_key.get_secret_value(),
        base_url=settings.memos_base_url,
    )
    rag_store = SqliteRagStore(
        settings.rag_db_path,
        embedder=create_embedding_provider(settings),
    )
    model = create_qwen_model(settings)
    agent = DeepAgentsResponder(model, tools=build_agent_tools(settings, rag_store))
    return AgentService(memory_store, agent, SupportPolicy()), memory_store, rag_store


def build_agent_tools(settings: Settings, rag_store: SqliteRagStore) -> list:
    tools = [build_rag_tool(rag_store)]
    if settings.search_configured:
        assert settings.dashscope_api_key is not None
        assert settings.dashscope_base_url is not None
        provider = AliyunWebSearchProvider(
            api_key=settings.dashscope_api_key.get_secret_value(),
            base_url=settings.dashscope_base_url,
            model=settings.search_model,
            timeout_seconds=settings.search_timeout_seconds,
        )
        tools.append(build_web_search_tool(provider))
    return tools
