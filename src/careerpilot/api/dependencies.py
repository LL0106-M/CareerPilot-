from careerpilot.agent.deepagents_runtime import DeepAgentsResponder
from careerpilot.agent.model import create_qwen_model
from careerpilot.agent.service import AgentService
from careerpilot.config import Settings
from careerpilot.memory.memos import MemosCloudMemoryStore
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.store import SqliteRagStore
from careerpilot.rag.tool import build_rag_tool
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
    agent = DeepAgentsResponder(model, tools=[build_rag_tool(rag_store)])
    return AgentService(memory_store, agent, SupportPolicy()), memory_store, rag_store
