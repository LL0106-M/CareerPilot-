from careerpilot.rag.models import KnowledgeOrigin

GRAPH_INDEX_DOMAINS = frozenset(
    {
        "preparation_material",
        "curated_document",
        "domain_knowledge",
        "ai_frontier",
    }
)


def allows_graph_index(domain: str, origin: KnowledgeOrigin) -> bool:
    """Only backend-curated professional knowledge may enter the public graph."""
    return origin is KnowledgeOrigin.SYSTEM_CURATED and domain in GRAPH_INDEX_DOMAINS
