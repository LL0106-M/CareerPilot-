from dataclasses import dataclass
from pathlib import Path

from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.loaders import load_markdown, load_pdf
from careerpilot.rag.models import SourceDocument
from careerpilot.rag.store import SqliteRagStore


@dataclass(frozen=True, slots=True)
class IndexingResult:
    documents: int
    chunks: int


class RagIndexer:
    def __init__(self, store: SqliteRagStore) -> None:
        self._store = store

    def ingest_document(self, document: SourceDocument) -> IndexingResult:
        if document.domain == "job_opportunity":
            chunks = chunk_document(document, max_chars=1_200, overlap_chars=100)
        else:
            chunks = chunk_document(document, max_chars=900, overlap_chars=100)
        self._store.upsert(document, chunks)
        return IndexingResult(documents=1, chunks=len(chunks))

    def ingest_markdown_directory(self, directory: Path) -> IndexingResult:
        documents = 0
        chunks = 0
        for path in sorted(directory.glob("*.md")):
            result = self.ingest_document(load_markdown(path))
            documents += result.documents
            chunks += result.chunks
        return IndexingResult(documents=documents, chunks=chunks)

    def ingest_pdf(self, path: Path, *, domain: str = "curated_document") -> IndexingResult:
        return self.ingest_document(load_pdf(path, domain=domain))

