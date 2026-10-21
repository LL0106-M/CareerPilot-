import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from careerpilot.config import Settings
from careerpilot.ingestion.pipeline import JobIngestionPipeline
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.store import SqliteRagStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize job search results and incrementally index them into CareerPilot RAG"
    )
    parser.add_argument("path", type=Path, help="UTF-8 JSON array following the job schema")
    parser.add_argument("--db", type=Path, default=Path("data/rag/careerpilot.db"))
    parser.add_argument("--fetched-at", help="ISO-8601 timestamp; defaults to current UTC time")
    args = parser.parse_args()
    records = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise SystemExit("input must be a JSON array of objects")
    fetched_at = datetime.fromisoformat(args.fetched_at) if args.fetched_at else datetime.now(UTC)
    settings = Settings()
    store = SqliteRagStore(args.db, embedder=create_embedding_provider(settings))
    try:
        result = JobIngestionPipeline(store, RagIndexer(store)).run(
            records,
            fetched_at=fetched_at,
        )
        print(json.dumps(asdict(result), ensure_ascii=False))
    finally:
        store.close()


if __name__ == "__main__":
    main()

