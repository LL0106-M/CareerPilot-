import argparse
from pathlib import Path

from careerpilot.agent.model import create_reasoning_model
from careerpilot.config import Settings
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.extraction import LlmGraphExtractor
from careerpilot.rag.indexer import IndexingResult, RagIndexer
from careerpilot.rag.models import KnowledgeOrigin
from careerpilot.rag.store import SqliteRagStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the CareerPilot local RAG index")
    parser.add_argument("--db", type=Path, default=Path("data/rag/careerpilot.db"))
    parser.add_argument("--markdown-dir", type=Path, action="append", default=[])
    parser.add_argument("--pdf", type=Path, action="append", default=[])
    parser.add_argument("--pdf-domain", default="ai_frontier")
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--directory", type=Path, action="append", default=[])
    parser.add_argument("--domain", default="preparation_material")
    parser.add_argument(
        "--origin",
        choices=tuple(origin.value for origin in KnowledgeOrigin),
        default=KnowledgeOrigin.SYSTEM_CURATED.value,
    )
    parser.add_argument("--owner-user-id")
    parser.add_argument("--asset-dir", type=Path, default=Path("data/rag/assets"))
    parser.add_argument("--extract-graph", action="store_true")
    parser.add_argument(
        "--allow-sparse-only",
        action="store_true",
        help="Allow offline indexing without dense vectors (development recovery only)",
    )
    parser.add_argument(
        "--graph-max-chunks",
        type=int,
        help="Sample at most this many child chunks for graph extraction (smoke tests only)",
    )
    args = parser.parse_args()

    settings = Settings()
    embedder = create_embedding_provider(settings)
    if embedder is None and not args.allow_sparse_only:
        parser.error(
            "offline indexing requires dense embeddings; configure "
            "CAREERPILOT_EMBEDDING_MODEL or pass --allow-sparse-only explicitly"
        )
    store = SqliteRagStore(
        args.db,
        embedder=embedder,
        strict_embeddings=not args.allow_sparse_only,
    )
    graph_extractor = (
        LlmGraphExtractor(
            create_reasoning_model(settings),
            max_chunks=args.graph_max_chunks,
        )
        if args.extract_graph
        else None
    )
    indexer = RagIndexer(store, graph_extractor=graph_extractor)
    total = None
    try:
        for directory in args.markdown_dir:
            result = indexer.ingest_markdown_directory(directory)
            total = result if total is None else total + result
        for path in args.pdf:
            result = indexer.ingest_pdf(path, domain=args.pdf_domain)
            total = result if total is None else total + result
        paths = list(args.file)
        for directory in args.directory:
            paths.extend(
                path
                for path in directory.rglob("*")
                if path.is_file()
                and path.suffix.lower() in {".md", ".markdown", ".txt", ".pdf", ".docx"}
            )
        origin = KnowledgeOrigin(args.origin)
        if origin is KnowledgeOrigin.USER_PROVIDED and not args.owner_user_id:
            parser.error("--owner-user-id is required when --origin=user_provided")
        for path in sorted(paths):
            result = indexer.ingest_file(
                path,
                domain=args.domain,
                knowledge_origin=origin,
                owner_user_id=args.owner_user_id,
                asset_dir=args.asset_dir,
            )
            total = result if total is None else total + result
        indexed = total or IndexingResult(0, 0)
        print(
            f"indexed_documents={indexed.documents} indexed_chunks={indexed.chunks} "
            f"indexed_evidence={indexed.evidence} graph_relations={indexed.graph_relations} "
            f"tables={indexed.tables} images={indexed.images} "
            f"sparse_entries={indexed.sparse_entries} dense_vectors={indexed.dense_vectors} "
            f"graph_nodes={indexed.graph_nodes} graph_edges={indexed.graph_edges} "
            f"total_documents={store.count_documents()} total_chunks={store.count_chunks()} "
            f"total_evidence={store.count_evidence()} total_images={store.count_image_assets()}"
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
