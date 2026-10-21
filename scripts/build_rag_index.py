import argparse
from pathlib import Path

from careerpilot.config import Settings
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.store import SqliteRagStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the CareerPilot local RAG index")
    parser.add_argument("--db", type=Path, default=Path("data/rag/careerpilot.db"))
    parser.add_argument("--markdown-dir", type=Path, action="append", default=[])
    parser.add_argument("--pdf", type=Path, action="append", default=[])
    parser.add_argument("--pdf-domain", default="ai_frontier")
    args = parser.parse_args()

    settings = Settings()
    store = SqliteRagStore(args.db, embedder=create_embedding_provider(settings))
    indexed_documents = 0
    indexed_chunks = 0
    try:
        for directory in args.markdown_dir:
            result = RagIndexer(store).ingest_markdown_directory(directory)
            indexed_documents += result.documents
            indexed_chunks += result.chunks
        for path in args.pdf:
            result = RagIndexer(store).ingest_pdf(path, domain=args.pdf_domain)
            indexed_documents += result.documents
            indexed_chunks += result.chunks
        print(
            f"indexed_documents={indexed_documents} indexed_chunks={indexed_chunks} "
            f"total_documents={store.count_documents()} total_chunks={store.count_chunks()} "
            f"total_evidence={store.count_evidence()}"
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
