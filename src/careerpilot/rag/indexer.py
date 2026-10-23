from dataclasses import dataclass
from pathlib import Path
from typing import Any

from careerpilot.rag.assets import build_image_assets
from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.evidence import build_evidence_units
from careerpilot.rag.extraction import GraphExtractor
from careerpilot.rag.loaders import load_document, load_markdown, load_pdf
from careerpilot.rag.models import ChunkLevel, EvidenceKind, KnowledgeOrigin, SourceDocument
from careerpilot.rag.policy import allows_graph_index
from careerpilot.rag.store import SqliteRagStore


@dataclass(frozen=True, slots=True)
class IndexingResult:
    documents: int
    chunks: int
    evidence: int = 0
    graph_relations: int = 0
    tables: int = 0
    images: int = 0
    sparse_entries: int = 0
    dense_vectors: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0

    def __add__(self, other: "IndexingResult") -> "IndexingResult":
        return IndexingResult(
            **{
                field: getattr(self, field) + getattr(other, field)
                for field in self.__dataclass_fields__
            }
        )


class RagIndexer:
    def __init__(
        self, store: SqliteRagStore, *, graph_extractor: GraphExtractor | None = None
    ) -> None:
        self._store = store
        self._graph_extractor = graph_extractor

    def ingest_document(self, document: SourceDocument) -> IndexingResult:
        if document.domain == "job_opportunity":
            chunks = chunk_document(document, max_chars=1_200, overlap_chars=100)
        else:
            chunks = chunk_document(document, max_chars=900, overlap_chars=100)
        triples: Any = None
        if self._graph_extractor and allows_graph_index(document.domain, document.knowledge_origin):
            triples = self._graph_extractor.extract(document, chunks)
        evidence = build_evidence_units(document, chunks, extracted_triples=triples)
        images = build_image_assets(document)
        self._store.upsert(document, chunks, evidence_units=evidence, image_assets=images)
        sparse_entries = self._store.count_sparse_entries(document_id=document.id)
        dense_vectors = self._store.count_dense_vectors(document_id=document.id)
        child_count = sum(chunk.chunk_level is ChunkLevel.CHILD for chunk in chunks)
        return IndexingResult(
            documents=1,
            chunks=child_count,
            evidence=len(evidence),
            graph_relations=sum(unit.kind is EvidenceKind.KG_TRIPLE for unit in evidence),
            tables=sum(unit.kind is EvidenceKind.TABLE for unit in evidence),
            images=len(images),
            sparse_entries=sparse_entries,
            dense_vectors=dense_vectors,
            graph_nodes=self._store.count_graph_nodes(document_id=document.id),
            graph_edges=self._store.count_graph_edges(document_id=document.id),
        )

    def ingest_markdown_directory(self, directory: Path) -> IndexingResult:
        total = IndexingResult(0, 0)
        for path in sorted(directory.glob("*.md")):
            result = self.ingest_document(load_markdown(path))
            total += result
        return total

    def ingest_pdf(self, path: Path, *, domain: str = "curated_document") -> IndexingResult:
        return self.ingest_document(load_pdf(path, domain=domain))

    def ingest_file(
        self,
        path: Path,
        *,
        domain: str = "curated_document",
        source_type: str = "developer_upload",
        knowledge_origin: KnowledgeOrigin = KnowledgeOrigin.SYSTEM_CURATED,
        owner_user_id: str | None = None,
        asset_dir: Path | None = None,
    ) -> IndexingResult:
        return self.ingest_document(
            load_document(
                path,
                domain=domain,
                source_type=source_type,
                knowledge_origin=knowledge_origin,
                owner_user_id=owner_user_id,
                asset_dir=asset_dir,
            )
        )
