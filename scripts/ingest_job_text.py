import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from careerpilot.agent.model import create_reasoning_model
from careerpilot.config import Settings
from careerpilot.ingestion.job_extraction import extract_job_record
from careerpilot.ingestion.pipeline import JobIngestionPipeline
from careerpilot.rag.embeddings import create_embedding_provider
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.store import SqliteRagStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and index one raw job posting")
    parser.add_argument("path", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-level", choices=("S", "A", "B", "C"), default="S")
    parser.add_argument("--source-name", default="")
    parser.add_argument("--db", type=Path, default=Path("data/rag/careerpilot.db"))
    parser.add_argument("--use-model", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    now = datetime.now(UTC)
    model = create_reasoning_model(settings) if args.use_model else None
    job = extract_job_record(
        args.path.read_text(encoding="utf-8"),
        source_url=args.source_url,
        source_level=args.source_level,
        source_name=args.source_name,
        verified_at=now.date().isoformat(),
        model=model,
    )
    store = SqliteRagStore(args.db, embedder=create_embedding_provider(settings))
    try:
        result = JobIngestionPipeline(store, RagIndexer(store)).run([asdict(job)], fetched_at=now)
        print(json.dumps(asdict(result), ensure_ascii=False))
    finally:
        store.close()


if __name__ == "__main__":
    main()
