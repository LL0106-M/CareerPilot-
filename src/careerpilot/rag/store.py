import hashlib
import json
import math
import re
import sqlite3
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from careerpilot.rag.assets import build_image_assets
from careerpilot.rag.embeddings import EmbeddingProvider
from careerpilot.rag.evidence import build_evidence_units
from careerpilot.rag.models import (
    DocumentChunk,
    EvidenceKind,
    EvidenceUnit,
    ImageAsset,
    KnowledgeOrigin,
    SearchHit,
    SourceDocument,
    WebSource,
)
from careerpilot.rag.policy import GRAPH_INDEX_DOMAINS, allows_graph_index


class SqliteRagStore:
    """Compact evidence store with sparse, optional dense, and local graph retrieval."""

    def __init__(
        self,
        path: Path,
        *,
        embedder: EmbeddingProvider | None = None,
        strict_embeddings: bool = False,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # FastAPI may execute requests on a worker thread different from the one
        # that initialized the local development store. Production uses a pooled
        # PostgreSQL/pgvector backend rather than sharing this SQLite connection.
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._embedder = embedder
        self._strict_embeddings = strict_embeddings
        self._query_vector_cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._query_vector_cache_lock = Lock()
        self._query_vector_cache_size = 256
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                source_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                published_at TEXT,
                fetched_at TEXT,
                knowledge_origin TEXT NOT NULL DEFAULT 'system_curated',
                owner_user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                title TEXT NOT NULL,
                heading TEXT NOT NULL,
                content TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                source_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                knowledge_origin TEXT NOT NULL DEFAULT 'system_curated',
                owner_user_id TEXT,
                parent_id TEXT,
                chunk_level TEXT NOT NULL DEFAULT 'child'
            );
            CREATE TABLE IF NOT EXISTS evidence_units (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                document_id TEXT NOT NULL,
                parent_id TEXT,
                title TEXT NOT NULL,
                embedding_text TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                source_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                vector_json TEXT,
                subject TEXT,
                predicate TEXT,
                object TEXT,
                knowledge_origin TEXT NOT NULL DEFAULT 'system_curated',
                owner_user_id TEXT
            );
            CREATE INDEX IF NOT EXISTS evidence_document_idx ON evidence_units(document_id);
            CREATE INDEX IF NOT EXISTS evidence_subject_idx ON evidence_units(subject);
            CREATE INDEX IF NOT EXISTS evidence_object_idx ON evidence_units(object);
            CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
                evidence_id UNINDEXED,
                title,
                embedding_text,
                tokenize='trigram'
            );
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                canonical_text TEXT NOT NULL,
                vector_json TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS graph_node_identity_idx
                ON graph_nodes(node_type, canonical_text);
            CREATE TABLE IF NOT EXISTS graph_node_sources (
                node_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                PRIMARY KEY (node_id, document_id, chunk_id, evidence_id)
            );
            CREATE INDEX IF NOT EXISTS graph_node_source_document_idx
                ON graph_node_sources(document_id);
            CREATE TABLE IF NOT EXISTS graph_edges (
                id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                predicate TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0
            );
            CREATE INDEX IF NOT EXISTS graph_edge_source_idx
                ON graph_edges(source_node_id);
            CREATE INDEX IF NOT EXISTS graph_edge_target_idx
                ON graph_edges(target_node_id);
            CREATE TABLE IF NOT EXISTS graph_edge_sources (
                edge_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                PRIMARY KEY (edge_id, evidence_id, document_id, chunk_id)
            );
            CREATE INDEX IF NOT EXISTS graph_edge_source_document_idx
                ON graph_edge_sources(document_id);
            CREATE TABLE IF NOT EXISTS image_assets (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                object_uri TEXT NOT NULL,
                image_type TEXT NOT NULL,
                bbox_json TEXT,
                caption TEXT,
                metadata_json TEXT NOT NULL,
                owner_user_id TEXT
            );
            CREATE INDEX IF NOT EXISTS image_document_idx
                ON image_assets(document_id, page_number);
            CREATE INDEX IF NOT EXISTS image_owner_idx
                ON image_assets(owner_user_id, document_id);
            CREATE TABLE IF NOT EXISTS source_registry (
                url TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                crawl_interval_hours INTEGER NOT NULL,
                status TEXT NOT NULL,
                last_crawled_at TEXT,
                content_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS job_records (
                id TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                role_title TEXT NOT NULL,
                role_family TEXT NOT NULL,
                recruiting_type TEXT NOT NULL,
                organization_type TEXT NOT NULL,
                employment_type TEXT NOT NULL,
                locations_json TEXT NOT NULL,
                deadline TEXT,
                apply_url TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_level TEXT NOT NULL,
                source_name TEXT NOT NULL,
                posted_at TEXT,
                verified_at TEXT NOT NULL,
                job_description TEXT NOT NULL,
                requirements TEXT NOT NULL,
                status TEXT NOT NULL,
                knowledge_origin TEXT NOT NULL DEFAULT 'system_curated',
                owner_user_id TEXT
            );
            CREATE INDEX IF NOT EXISTS jobs_org_idx ON job_records(organization_type);
            CREATE INDEX IF NOT EXISTS jobs_company_idx ON job_records(company_name);
            CREATE INDEX IF NOT EXISTS jobs_owner_idx ON job_records(owner_user_id);
            CREATE TABLE IF NOT EXISTS user_documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                file_format TEXT NOT NULL,
                size_text TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                status TEXT NOT NULL,
                retrieval_enabled INTEGER NOT NULL DEFAULT 1,
                owner_user_id TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS user_docs_owner_idx ON user_documents(owner_user_id);
            """
        )
        self._ensure_column(
            "documents", "knowledge_origin", "TEXT NOT NULL DEFAULT 'system_curated'"
        )
        self._ensure_column("documents", "owner_user_id", "TEXT")
        self._ensure_column(
            "chunks", "knowledge_origin", "TEXT NOT NULL DEFAULT 'system_curated'"
        )
        self._ensure_column("chunks", "owner_user_id", "TEXT")
        self._ensure_column("chunks", "parent_id", "TEXT")
        self._ensure_column("chunks", "chunk_level", "TEXT NOT NULL DEFAULT 'child'")
        self._ensure_column(
            "evidence_units", "knowledge_origin", "TEXT NOT NULL DEFAULT 'system_curated'"
        )
        self._ensure_column("evidence_units", "owner_user_id", "TEXT")
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS evidence_owner_idx "
            "ON evidence_units(owner_user_id, knowledge_origin)"
        )

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            str(row["name"])
            for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def upsert(
        self,
        document: SourceDocument,
        chunks: tuple[DocumentChunk, ...],
        evidence_units: tuple[EvidenceUnit, ...] | None = None,
        image_assets: tuple[ImageAsset, ...] | None = None,
    ) -> None:
        units = evidence_units or build_evidence_units(document, chunks)
        images = image_assets if image_assets is not None else build_image_assets(document)
        vectors = self._embed_units(units)
        graph_records = self._prepare_graph_records(document, units)
        with self._connection:
            self._remove_document_graph(document.id)
            previous_units = self._connection.execute(
                "SELECT id FROM evidence_units WHERE document_id = ?", (document.id,)
            ).fetchall()
            for row in previous_units:
                self._connection.execute(
                    "DELETE FROM evidence_fts WHERE evidence_id = ?", (row["id"],)
                )
            self._connection.execute(
                "DELETE FROM evidence_units WHERE document_id = ?", (document.id,)
            )
            self._connection.execute("DELETE FROM chunks WHERE document_id = ?", (document.id,))
            self._connection.execute(
                "DELETE FROM image_assets WHERE document_id = ?", (document.id,)
            )
            self._connection.execute(
                """
                INSERT OR REPLACE INTO documents
                (id, title, source_uri, source_type, domain, text, metadata_json,
                 published_at, fetched_at, knowledge_origin, owner_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.title,
                    document.source_uri,
                    document.source_type,
                    document.domain,
                    document.text,
                    json.dumps(document.metadata, ensure_ascii=False),
                    document.published_at,
                    document.fetched_at,
                    document.knowledge_origin.value,
                    document.owner_user_id,
                ),
            )
            for chunk in chunks:
                self._connection.execute(
                    """
                    INSERT INTO chunks
                    (id, document_id, ordinal, title, heading, content, source_uri,
                     source_type, domain, metadata_json, knowledge_origin, owner_user_id,
                     parent_id, chunk_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.ordinal,
                        chunk.title,
                        chunk.heading,
                        chunk.content,
                        chunk.source_uri,
                        chunk.source_type,
                        chunk.domain,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        chunk.knowledge_origin.value,
                        chunk.owner_user_id,
                        chunk.parent_id,
                        chunk.chunk_level.value,
                    ),
                )
            for asset in images:
                self._insert_image_asset(asset)
            for unit, vector in zip(units, vectors, strict=True):
                self._insert_evidence(unit, vector)
            self._insert_graph_records(*graph_records)

    def _prepare_graph_records(
        self,
        document: SourceDocument,
        units: tuple[EvidenceUnit, ...],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        if not allows_graph_index(document.domain, document.knowledge_origin):
            return [], []
        triples = [unit for unit in units if unit.kind is EvidenceKind.KG_TRIPLE]
        passages = {
            str(unit.metadata.get("chunk_id")): unit
            for unit in units
            if unit.kind is EvidenceKind.PASSAGE
        }
        phrase_texts = sorted(
            {
                text
                for unit in triples
                for text in (unit.subject, unit.object)
                if text
            }
        )
        phrase_vectors = self._embed_texts(phrase_texts)
        vector_by_phrase = dict(zip(phrase_texts, phrase_vectors, strict=True))
        nodes: list[dict[str, object]] = []
        edges: list[dict[str, object]] = []
        seen_node_sources: set[tuple[str, str, str]] = set()
        seen_edge_sources: set[tuple[str, str, str]] = set()

        def add_node(record: dict[str, object]) -> None:
            key = (
                str(record["id"]),
                str(record["chunk_id"]),
                str(record["evidence_id"]),
            )
            if key not in seen_node_sources:
                seen_node_sources.add(key)
                nodes.append(record)

        def add_edge(record: dict[str, object]) -> None:
            key = (
                str(record["id"]),
                str(record["chunk_id"]),
                str(record["evidence_id"]),
            )
            if key not in seen_edge_sources:
                seen_edge_sources.add(key)
                edges.append(record)

        for chunk_id, passage in passages.items():
            passage_node_id = _graph_node_id("passage", passage.id)
            add_node(
                {
                    "id": passage_node_id,
                    "node_type": "passage",
                    "canonical_text": passage.id,
                    "vector": None,
                    "document_id": document.id,
                    "chunk_id": chunk_id,
                    "evidence_id": passage.id,
                }
            )

        for triple in triples:
            chunk_id = str(triple.metadata.get("chunk_id") or triple.parent_id or "")
            passage = passages.get(chunk_id)
            if passage is None or not triple.subject or not triple.object:
                continue
            passage_node_id = _graph_node_id("passage", passage.id)
            phrase_ids: list[str] = []
            for phrase in (triple.subject, triple.object):
                phrase_id = _graph_node_id("phrase", _canonical_phrase(phrase))
                phrase_ids.append(phrase_id)
                add_node({
                    "id": phrase_id,
                    "node_type": "phrase",
                    "canonical_text": phrase,
                    "vector": vector_by_phrase.get(phrase),
                    "document_id": document.id,
                    "chunk_id": chunk_id,
                    "evidence_id": triple.id,
                })
                contains_id = _graph_edge_id(passage_node_id, "contains", phrase_id)
                add_edge({
                    "id": contains_id,
                    "source": passage_node_id,
                    "target": phrase_id,
                    "edge_type": "contains",
                    "predicate": "contains",
                    "weight": 1.0,
                    "evidence_id": triple.id,
                    "document_id": document.id,
                    "chunk_id": chunk_id,
                })
            relation_id = _graph_edge_id(
                phrase_ids[0], triple.predicate or "related_to", phrase_ids[1]
            )
            add_edge({
                "id": relation_id,
                "source": phrase_ids[0],
                "target": phrase_ids[1],
                "edge_type": "relation",
                "predicate": triple.predicate or "related_to",
                "weight": 1.0,
                "evidence_id": triple.id,
                "document_id": document.id,
                "chunk_id": chunk_id,
            })
        return nodes, edges

    def _embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        if self._embedder is None:
            if self._strict_embeddings:
                raise RuntimeError("dense graph indexing requires an embedding provider")
            return [None] * len(texts)
        try:
            vectors = self._embedder.embed_documents(texts)
        except Exception as exc:
            if self._strict_embeddings:
                raise RuntimeError("dense graph-node indexing failed") from exc
            return [None] * len(texts)
        if len(vectors) != len(texts):
            if self._strict_embeddings:
                raise RuntimeError("graph-node vector count does not match phrase count")
            return [None] * len(texts)
        return [list(vector) for vector in vectors]

    def _remove_document_graph(self, document_id: str) -> None:
        self._connection.execute(
            "DELETE FROM graph_edge_sources WHERE document_id = ?", (document_id,)
        )
        self._connection.execute(
            "DELETE FROM graph_node_sources WHERE document_id = ?", (document_id,)
        )
        self._connection.execute(
            "DELETE FROM graph_edges WHERE edge_type <> 'synonym' AND id NOT IN "
            "(SELECT DISTINCT edge_id FROM graph_edge_sources)"
        )
        self._connection.execute(
            "DELETE FROM graph_nodes WHERE id NOT IN "
            "(SELECT DISTINCT node_id FROM graph_node_sources)"
        )
        self._connection.execute(
            "DELETE FROM graph_edges WHERE source_node_id NOT IN (SELECT id FROM graph_nodes) "
            "OR target_node_id NOT IN (SELECT id FROM graph_nodes)"
        )

    def _insert_graph_records(
        self,
        nodes: list[dict[str, object]],
        edges: list[dict[str, object]],
    ) -> None:
        for node in nodes:
            vector = node["vector"]
            self._connection.execute(
                """
                INSERT INTO graph_nodes (id, node_type, canonical_text, vector_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    vector_json = COALESCE(graph_nodes.vector_json, excluded.vector_json)
                """,
                (
                    node["id"],
                    node["node_type"],
                    node["canonical_text"],
                    json.dumps(vector) if vector is not None else None,
                ),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO graph_node_sources
                (node_id, document_id, chunk_id, evidence_id) VALUES (?, ?, ?, ?)
                """,
                (
                    node["id"],
                    node["document_id"],
                    node["chunk_id"],
                    node["evidence_id"],
                ),
            )
        for edge in edges:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO graph_edges
                (id, source_node_id, target_node_id, edge_type, predicate, weight)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edge["id"],
                    edge["source"],
                    edge["target"],
                    edge["edge_type"],
                    edge["predicate"],
                    edge["weight"],
                ),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO graph_edge_sources
                (edge_id, evidence_id, document_id, chunk_id) VALUES (?, ?, ?, ?)
                """,
                (
                    edge["id"],
                    edge["evidence_id"],
                    edge["document_id"],
                    edge["chunk_id"],
                ),
            )
        self._add_synonym_edges(tuple(str(node["id"]) for node in nodes))

    def _add_synonym_edges(self, candidate_node_ids: tuple[str, ...]) -> None:
        phrase_rows = self._connection.execute(
            "SELECT * FROM graph_nodes WHERE node_type = 'phrase' AND vector_json IS NOT NULL"
        ).fetchall()
        by_id = {str(row["id"]): row for row in phrase_rows}
        candidates = [node_id for node_id in dict.fromkeys(candidate_node_ids) if node_id in by_id]
        for node_id in candidates:
            vector = json.loads(by_id[node_id]["vector_json"])
            neighbors = sorted(
                (
                    (_cosine_similarity(vector, json.loads(row["vector_json"])), other_id)
                    for other_id, row in by_id.items()
                    if other_id != node_id
                ),
                reverse=True,
            )[:5]
            for score, other_id in neighbors:
                if score < 0.8:
                    continue
                source, target = sorted((node_id, other_id))
                edge_id = _graph_edge_id(source, "synonym", target)
                self._connection.execute(
                    """
                    INSERT OR REPLACE INTO graph_edges
                    (id, source_node_id, target_node_id, edge_type, predicate, weight)
                    VALUES (?, ?, ?, 'synonym', 'synonym', ?)
                    """,
                    (edge_id, source, target, score),
                )

    def _insert_image_asset(self, asset: ImageAsset) -> None:
        self._connection.execute(
            """
            INSERT INTO image_assets
            (id, document_id, page_number, object_uri, image_type, bbox_json,
             caption, metadata_json, owner_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset.id,
                asset.document_id,
                asset.page_number,
                asset.object_uri,
                asset.image_type,
                json.dumps(asset.bbox) if asset.bbox is not None else None,
                asset.caption,
                json.dumps(asset.metadata, ensure_ascii=False),
                asset.owner_user_id,
            ),
        )

    def _embed_units(self, units: tuple[EvidenceUnit, ...]) -> list[list[float] | None]:
        if not units:
            return [None] * len(units)
        if self._embedder is None:
            if self._strict_embeddings:
                raise RuntimeError(
                    "dense indexing is required, but no embedding provider is configured"
                )
            return [None] * len(units)
        try:
            vectors = self._embedder.embed_documents([unit.embedding_text for unit in units])
        except Exception as exc:
            if self._strict_embeddings:
                raise RuntimeError("dense indexing failed; document was not replaced") from exc
            return [None] * len(units)
        if len(vectors) != len(units):
            if self._strict_embeddings:
                raise RuntimeError(
                    "dense indexing returned a different number of vectors than evidence units"
                )
            return [None] * len(units)
        return [list(vector) for vector in vectors]

    def _insert_evidence(self, unit: EvidenceUnit, vector: list[float] | None) -> None:
        self._connection.execute(
            """
            INSERT INTO evidence_units
            (id, kind, document_id, parent_id, title, embedding_text, source_uri,
             source_type, domain, metadata_json, vector_json, subject, predicate, object,
             knowledge_origin, owner_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                unit.id,
                unit.kind.value,
                unit.document_id,
                unit.parent_id,
                unit.title,
                unit.embedding_text,
                unit.source_uri,
                unit.source_type,
                unit.domain,
                json.dumps(unit.metadata, ensure_ascii=False),
                json.dumps(vector) if vector is not None else None,
                unit.subject,
                unit.predicate,
                unit.object,
                unit.knowledge_origin.value,
                unit.owner_user_id,
            ),
        )
        self._connection.execute(
            "INSERT INTO evidence_fts (evidence_id, title, embedding_text) VALUES (?, ?, ?)",
            (unit.id, unit.title, unit.embedding_text),
        )

    def search(
        self,
        query: str,
        *,
        domain: str | None = None,
        user_id: str | None = None,
        origins: frozenset[KnowledgeOrigin] | None = None,
        limit: int = 5,
    ) -> tuple[SearchHit, ...]:
        return self.search_sparse(
            query, domain=domain, user_id=user_id, origins=origins, limit=limit
        )

    def search_sparse(
        self,
        query: str,
        *,
        domain: str | None = None,
        kinds: frozenset[EvidenceKind] | None = None,
        user_id: str | None = None,
        origins: frozenset[KnowledgeOrigin] | None = None,
        limit: int = 5,
    ) -> tuple[SearchHit, ...]:
        match_query = _fts_query(query)
        if not match_query:
            return ()
        params: list[object] = [match_query]
        filters: list[str] = []
        if domain is not None:
            filters.append("e.domain = ?")
            params.append(domain)
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            filters.append(f"e.kind IN ({placeholders})")
            params.extend(kind.value for kind in sorted(kinds, key=lambda item: item.value))
        _append_access_filters(filters, params, user_id=user_id, origins=origins, prefix="e.")
        where = f"AND {' AND '.join(filters)}" if filters else ""
        params.append(max(1, min(limit, 100)))
        rows = self._connection.execute(
            f"""
            SELECT e.*, bm25(evidence_fts, 0.0, 2.0, 1.0) AS rank
            FROM evidence_fts
            JOIN evidence_units e ON e.id = evidence_fts.evidence_id
            WHERE evidence_fts MATCH ? {where}
            ORDER BY rank
            LIMIT ?
            """,
            params,
        ).fetchall()
        if not rows:
            rows = self._search_short_terms(
                query,
                domain=domain,
                kinds=kinds,
                user_id=user_id,
                origins=origins,
                limit=limit,
            )
        return tuple(
            self._row_to_hit(
                row,
                score=(
                    1.0 / (1.0 + abs(float(row["rank"])))
                    if "rank" in row.keys()
                    else 0.5
                ),
                channels=("sparse",),
            )
            for row in rows
        )

    def _search_short_terms(
        self,
        query: str,
        *,
        domain: str | None,
        kinds: frozenset[EvidenceKind] | None,
        user_id: str | None,
        origins: frozenset[KnowledgeOrigin] | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        terms = re.findall(r"[\u4e00-\u9fff]{2}", query)
        if not terms:
            return []
        clauses = ["(" + " OR ".join("embedding_text LIKE ?" for _ in terms) + ")"]
        params: list[object] = [f"%{term}%" for term in terms]
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kind.value for kind in sorted(kinds, key=lambda item: item.value))
        _append_access_filters(clauses, params, user_id=user_id, origins=origins)
        params.append(max(1, min(limit, 100)))
        return self._connection.execute(
            f"""
            SELECT * FROM evidence_units
            WHERE {' AND '.join(clauses)}
            ORDER BY id
            LIMIT ?
            """,
            params,
        ).fetchall()

    def search_dense(
        self,
        query: str,
        *,
        query_vector: tuple[float, ...] | list[float] | None = None,
        domain: str | None = None,
        kinds: frozenset[EvidenceKind] | None = None,
        user_id: str | None = None,
        origins: frozenset[KnowledgeOrigin] | None = None,
        limit: int = 5,
    ) -> tuple[SearchHit, ...]:
        if not query.strip():
            return ()
        if query_vector is None:
            query_vector = self.embed_query(query)
        if query_vector is None:
            return ()
        clauses = ["vector_json IS NOT NULL"]
        params: list[object] = []
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kind.value for kind in sorted(kinds, key=lambda item: item.value))
        _append_access_filters(clauses, params, user_id=user_id, origins=origins)
        rows = self._connection.execute(
            f"SELECT * FROM evidence_units WHERE {' AND '.join(clauses)}", params
        ).fetchall()
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            vector = json.loads(row["vector_json"])
            scored.append((_cosine_similarity(query_vector, vector), row))
        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        return tuple(
            self._row_to_hit(row, score=score, channels=("dense",))
            for score, row in scored[: max(1, min(limit, 100))]
        )

    def embed_query(self, query: str) -> tuple[float, ...] | None:
        """Embed a normalized query once and reuse it across evidence kinds/domains."""
        normalized = " ".join(query.split()).strip()
        if self._embedder is None or not normalized:
            return None
        with self._query_vector_cache_lock:
            cached = self._query_vector_cache.get(normalized)
            if cached is not None:
                self._query_vector_cache.move_to_end(normalized)
                return cached
        try:
            vector = tuple(float(value) for value in self._embedder.embed_query(normalized))
        except Exception:
            return None
        with self._query_vector_cache_lock:
            self._query_vector_cache[normalized] = vector
            self._query_vector_cache.move_to_end(normalized)
            while len(self._query_vector_cache) > self._query_vector_cache_size:
                self._query_vector_cache.popitem(last=False)
        return vector

    def neighbors(
        self,
        evidence_ids: Iterable[str | None],
        *,
        user_id: str | None = None,
        origins: frozenset[KnowledgeOrigin] | None = None,
        limit: int = 10,
    ) -> tuple[SearchHit, ...]:
        seed_ids = tuple(dict.fromkeys(item for item in evidence_ids if item))
        if not seed_ids:
            return ()
        placeholders = ",".join("?" for _ in seed_ids)
        seeds = self._connection.execute(
            f"""
            SELECT subject, object FROM evidence_units
            WHERE id IN ({placeholders}) AND kind = ?
            """,
            (*seed_ids, EvidenceKind.KG_TRIPLE.value),
        ).fetchall()
        nodes = {value for row in seeds for value in (row["subject"], row["object"]) if value}
        if not nodes:
            return ()
        node_placeholders = ",".join("?" for _ in nodes)
        access_filters: list[str] = []
        access_params: list[object] = []
        _append_access_filters(
            access_filters,
            access_params,
            user_id=user_id,
            origins=origins,
        )
        access_where = " AND ".join(access_filters)
        rows = self._connection.execute(
            f"""
            SELECT * FROM evidence_units
            WHERE kind = ?
              AND (subject IN ({node_placeholders}) OR object IN ({node_placeholders}))
              AND id NOT IN ({placeholders})
              AND parent_id IS NOT NULL
              AND source_uri <> ''
              AND {access_where}
            ORDER BY id
            LIMIT ?
            """,
            (
                EvidenceKind.KG_TRIPLE.value,
                *nodes,
                *nodes,
                *seed_ids,
                *access_params,
                max(1, min(limit, 100)),
            ),
        ).fetchall()
        return tuple(self._row_to_hit(row, score=0.0, channels=("graph",)) for row in rows)

    def search_graph_ppr(
        self,
        seeds: Iterable[SearchHit],
        *,
        domain: str | None = None,
        user_id: str | None = None,
        origins: frozenset[KnowledgeOrigin] | None = None,
        limit: int = 10,
        graph_mode: str = "local",
        passage_node_weight: float = 0.05,
        damping: float = 0.5,
        iterations: int = 20,
    ) -> tuple[SearchHit, ...]:
        """Run bounded HippoRAG-style PPR and return passage evidence only."""
        seed_hits = tuple(seeds)
        if not seed_hits:
            return ()
        filters: list[str] = []
        params: list[object] = []
        if domain is not None:
            filters.append("e.domain = ?")
            params.append(domain)
        _append_access_filters(filters, params, user_id=user_id, origins=origins, prefix="e.")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self._connection.execute(
            f"""
            SELECT DISTINCT n.id, n.node_type
            FROM graph_nodes n
            JOIN graph_node_sources s ON s.node_id = n.id
            JOIN evidence_units e ON e.id = s.evidence_id
            {where}
            """,
            params,
        ).fetchall()
        allowed = {str(row["id"]): str(row["node_type"]) for row in rows}
        if not allowed:
            return ()

        reset: dict[str, float] = {}
        triple_ids = tuple(
            hit.evidence_id
            for hit in seed_hits
            if hit.evidence_kind is EvidenceKind.KG_TRIPLE and hit.evidence_id
        )
        triple_nodes: dict[str, tuple[str, str]] = {}
        if triple_ids:
            placeholders = ",".join("?" for _ in triple_ids)
            triple_rows = self._connection.execute(
                f"SELECT id, subject, object FROM evidence_units WHERE id IN ({placeholders})",
                triple_ids,
            ).fetchall()
            triple_nodes = {
                str(row["id"]): (
                    _graph_node_id("phrase", _canonical_phrase(str(row["subject"]))),
                    _graph_node_id("phrase", _canonical_phrase(str(row["object"]))),
                )
                for row in triple_rows
                if row["subject"] and row["object"]
            }
        for rank, hit in enumerate(seed_hits, 1):
            weight = max(hit.score, 0.0) + 1.0 / rank
            if hit.evidence_kind is EvidenceKind.PASSAGE and hit.evidence_id:
                node_ids = (_graph_node_id("passage", hit.evidence_id),)
                weight *= max(0.0, passage_node_weight)
            elif hit.evidence_id in triple_nodes:
                node_ids = triple_nodes[hit.evidence_id]
            else:
                node_ids = ()
            for node_id in node_ids:
                if node_id in allowed:
                    reset[node_id] = reset.get(node_id, 0.0) + weight
        if not reset:
            return ()
        if graph_mode == "local":
            local_ids = self._bounded_graph_nodes(
                tuple(reset),
                permitted=frozenset(allowed),
                max_hops=2,
                max_nodes=500,
            )
            allowed = {node_id: allowed[node_id] for node_id in local_ids}
            reset = {node_id: score for node_id, score in reset.items() if node_id in allowed}
            if not reset:
                return ()
        total_reset = sum(reset.values())
        reset = {node_id: score / total_reset for node_id, score in reset.items()}

        placeholders = ",".join("?" for _ in allowed)
        edge_rows = self._connection.execute(
            f"""
            SELECT source_node_id, target_node_id, weight
            FROM graph_edges
            WHERE source_node_id IN ({placeholders})
              AND target_node_id IN ({placeholders})
            """,
            (*allowed, *allowed),
        ).fetchall()
        adjacency: dict[str, dict[str, float]] = {node_id: {} for node_id in allowed}
        for row in edge_rows:
            source = str(row["source_node_id"])
            target = str(row["target_node_id"])
            weight = max(float(row["weight"]), 0.0)
            adjacency[source][target] = adjacency[source].get(target, 0.0) + weight
            adjacency[target][source] = adjacency[target].get(source, 0.0) + weight

        scores = dict(reset)
        for _ in range(max(1, min(iterations, 100))):
            updated = {
                node_id: (1.0 - damping) * reset.get(node_id, 0.0) for node_id in allowed
            }
            dangling = 0.0
            for source, source_score in scores.items():
                neighbors = adjacency.get(source, {})
                total_weight = sum(neighbors.values())
                if total_weight <= 0:
                    dangling += source_score
                    continue
                for target, weight in neighbors.items():
                    updated[target] += damping * source_score * weight / total_weight
            if dangling:
                for node_id, probability in reset.items():
                    updated[node_id] += damping * dangling * probability
            scores = updated

        ranked_passages = [
            (score, node_id)
            for node_id, score in scores.items()
            if allowed[node_id] == "passage" and score > 0
        ]
        ranked_passages.sort(key=lambda item: (-item[0], item[1]))
        results: list[SearchHit] = []
        for score, node_id in ranked_passages[: max(1, min(limit, 100))]:
            row = self._connection.execute(
                """
                SELECT e.*
                FROM graph_node_sources s
                JOIN evidence_units e ON e.id = s.evidence_id
                WHERE s.node_id = ? AND e.kind = ?
                LIMIT 1
                """,
                (node_id, EvidenceKind.PASSAGE.value),
            ).fetchone()
            if row is not None:
                results.append(self._row_to_hit(row, score=score, channels=("graph", "ppr")))
        return tuple(results)

    def _bounded_graph_nodes(
        self,
        seed_ids: tuple[str, ...],
        *,
        permitted: frozenset[str],
        max_hops: int,
        max_nodes: int,
    ) -> tuple[str, ...]:
        """Collect a deterministic, access-filtered induced neighborhood."""
        visited = {node_id for node_id in seed_ids if node_id in permitted}
        frontier = set(visited)
        for _ in range(max(0, min(max_hops, 5))):
            if not frontier or len(visited) >= max_nodes:
                break
            placeholders = ",".join("?" for _ in frontier)
            rows = self._connection.execute(
                f"""
                SELECT source_node_id, target_node_id
                FROM graph_edges
                WHERE source_node_id IN ({placeholders})
                   OR target_node_id IN ({placeholders})
                ORDER BY id
                """,
                (*frontier, *frontier),
            ).fetchall()
            candidates = {
                str(value)
                for row in rows
                for value in (row["source_node_id"], row["target_node_id"])
                if str(value) in permitted and str(value) not in visited
            }
            remaining = max_nodes - len(visited)
            frontier = set(sorted(candidates)[:remaining])
            visited.update(frontier)
        return tuple(sorted(visited))

    def _row_to_hit(
        self,
        row: sqlite3.Row,
        *,
        score: float,
        channels: tuple[str, ...],
    ) -> SearchHit:
        metadata = json.loads(row["metadata_json"])
        if row["kind"] == EvidenceKind.KG_TRIPLE.value:
            metadata = {
                **metadata,
                "subject": row["subject"],
                "predicate": row["predicate"],
                "object": row["object"],
            }
        evidence_id = str(row["id"])
        return SearchHit(
            chunk_id=str(metadata.get("chunk_id") or evidence_id),
            document_id=str(row["document_id"]),
            title=str(row["title"]),
            heading=str(metadata.get("heading") or row["kind"]),
            content=str(row["embedding_text"]),
            source_uri=str(row["source_uri"]),
            source_type=str(row["source_type"]),
            domain=str(row["domain"]),
            score=score,
            metadata=metadata,
            evidence_id=evidence_id,
            evidence_kind=EvidenceKind(row["kind"]),
            parent_id=row["parent_id"],
            channels=channels,
            knowledge_origin=KnowledgeOrigin(row["knowledge_origin"]),
            owner_user_id=row["owner_user_id"],
        )

    def expand_parent_context(self, hits: tuple[SearchHit, ...]) -> tuple[SearchHit, ...]:
        """Replace matched child text with its parent context without losing provenance."""
        anchor_ids = tuple(dict.fromkeys(hit.parent_id for hit in hits if hit.parent_id))
        rows = self._chunk_rows(anchor_ids)
        parent_ids = tuple(
            dict.fromkeys(
                str(row["parent_id"])
                for row in rows.values()
                if row["chunk_level"] == "child" and row["parent_id"]
            )
        )
        rows.update(self._chunk_rows(parent_ids))

        expanded: list[SearchHit] = []
        for hit in hits:
            anchor = rows.get(hit.parent_id or "")
            parent = anchor
            if anchor is not None and anchor["chunk_level"] == "child" and anchor["parent_id"]:
                parent = rows.get(str(anchor["parent_id"]))
            if parent is None or parent["chunk_level"] != "parent":
                expanded.append(hit)
                continue
            matched_chunk_id = str(hit.metadata.get("chunk_id") or (anchor or parent)["id"])
            metadata = {
                **hit.metadata,
                "matched_chunk_id": matched_chunk_id,
                "matched_content": hit.content,
                "matched_heading": hit.heading,
                "context_chunk_id": str(parent["id"]),
                "context_chunk_level": "parent",
            }
            expanded.append(
                replace(
                    hit,
                    heading=str(parent["heading"]),
                    content=str(parent["content"]),
                    metadata=metadata,
                    parent_id=str(parent["id"]),
                )
            )
        return tuple(expanded)

    def _chunk_rows(self, chunk_ids: tuple[str, ...]) -> dict[str, sqlite3.Row]:
        if not chunk_ids:
            return {}
        placeholders = ",".join("?" for _ in chunk_ids)
        rows = self._connection.execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})", chunk_ids
        ).fetchall()
        return {str(row["id"]): row for row in rows}

    def count_documents(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM documents").fetchone()
        return int(row["count"])

    def count_chunks(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()
        return int(row["count"])

    def count_evidence(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM evidence_units").fetchone()
        return int(row["count"])

    def count_sparse_entries(self, *, document_id: str | None = None) -> int:
        if document_id is None:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM evidence_fts"
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM evidence_fts f
                JOIN evidence_units e ON e.id = f.evidence_id
                WHERE e.document_id = ?
                """,
                (document_id,),
            ).fetchone()
        return int(row["count"])

    def count_dense_vectors(self, *, document_id: str | None = None) -> int:
        if document_id is None:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM evidence_units WHERE vector_json IS NOT NULL"
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM evidence_units
                WHERE vector_json IS NOT NULL AND document_id = ?
                """,
                (document_id,),
            ).fetchone()
        return int(row["count"])

    def count_graph_nodes(
        self, *, node_type: str | None = None, document_id: str | None = None
    ) -> int:
        filters: list[str] = []
        params: list[object] = []
        if node_type is not None:
            filters.append("n.node_type = ?")
            params.append(node_type)
        if document_id is not None:
            filters.append("s.document_id = ?")
            params.append(document_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        join = "JOIN graph_node_sources s ON s.node_id = n.id" if document_id else ""
        row = self._connection.execute(
            f"SELECT COUNT(DISTINCT n.id) AS count FROM graph_nodes n {join} {where}", params
        ).fetchone()
        return int(row["count"])

    def count_graph_edges(
        self, *, edge_type: str | None = None, document_id: str | None = None
    ) -> int:
        filters: list[str] = []
        params: list[object] = []
        if edge_type is not None:
            filters.append("g.edge_type = ?")
            params.append(edge_type)
        if document_id is not None:
            filters.append("s.document_id = ?")
            params.append(document_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        join = "JOIN graph_edge_sources s ON s.edge_id = g.id" if document_id else ""
        row = self._connection.execute(
            f"SELECT COUNT(DISTINCT g.id) AS count FROM graph_edges g {join} {where}", params
        ).fetchone()
        return int(row["count"])

    def index_health(self) -> dict[str, object]:
        evidence = self.count_evidence()
        sparse = self.count_sparse_entries()
        dense = self.count_dense_vectors()
        placeholders = ",".join("?" for _ in GRAPH_INDEX_DOMAINS)
        graph_passages_expected = int(
            self._connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM evidence_units
                WHERE kind = ? AND knowledge_origin = ?
                  AND domain IN ({placeholders})
                """,
                (
                    EvidenceKind.PASSAGE.value,
                    KnowledgeOrigin.SYSTEM_CURATED.value,
                    *sorted(GRAPH_INDEX_DOMAINS),
                ),
            ).fetchone()["count"]
        )
        graph_passages = int(
            self._connection.execute(
                f"""
                SELECT COUNT(DISTINCT s.evidence_id) AS count
                FROM graph_node_sources s
                JOIN graph_nodes n ON n.id = s.node_id
                JOIN evidence_units e ON e.id = s.evidence_id
                WHERE n.node_type = 'passage' AND e.knowledge_origin = ?
                  AND e.domain IN ({placeholders})
                """,
                (
                    KnowledgeOrigin.SYSTEM_CURATED.value,
                    *sorted(GRAPH_INDEX_DOMAINS),
                ),
            ).fetchone()["count"]
        )
        graph_triples = int(
            self._connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM evidence_units
                WHERE kind = ? AND knowledge_origin = ?
                  AND domain IN ({placeholders})
                """,
                (
                    EvidenceKind.KG_TRIPLE.value,
                    KnowledgeOrigin.SYSTEM_CURATED.value,
                    *sorted(GRAPH_INDEX_DOMAINS),
                ),
            ).fetchone()["count"]
        )
        relation_edges = self.count_graph_edges(edge_type="relation")
        graph_ready = graph_passages == graph_passages_expected and (
            graph_passages_expected == 0 or (graph_triples > 0 and relation_edges > 0)
        )
        ready = (
            evidence > 0
            and sparse == evidence
            and dense == evidence
            and graph_ready
        )
        return {
            "ready": ready,
            "evidence": evidence,
            "sparse_entries": sparse,
            "dense_vectors": dense,
            "graph_passages": graph_passages,
            "graph_passages_expected": graph_passages_expected,
            "graph_triples": graph_triples,
            "relation_edges": relation_edges,
            "graph_nodes": self.count_graph_nodes(),
            "graph_edges": self.count_graph_edges(),
        }

    def count_image_assets(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM image_assets").fetchone()
        return int(row["count"])

    def source_content_hash(self, url: str) -> str | None:
        row = self._connection.execute(
            "SELECT content_hash FROM source_registry WHERE url = ?", (url,)
        ).fetchone()
        if row is None or row["content_hash"] is None:
            return None
        return str(row["content_hash"])

    def register_source(self, source: WebSource) -> None:
        if source.crawl_interval_hours < 1:
            raise ValueError("crawl_interval_hours must be positive")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO source_registry
                (url, source_type, domain, crawl_interval_hours, status,
                 last_crawled_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    source_type = excluded.source_type,
                    domain = excluded.domain,
                    crawl_interval_hours = excluded.crawl_interval_hours,
                    status = excluded.status
                """,
                (
                    source.url,
                    source.source_type,
                    source.domain,
                    source.crawl_interval_hours,
                    source.status,
                    source.last_crawled_at,
                    source.content_hash,
                ),
            )

    def mark_source_crawled(
        self,
        url: str,
        *,
        crawled_at: datetime,
        content_hash: str,
    ) -> None:
        normalized = _as_utc(crawled_at).isoformat()
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE source_registry
                SET last_crawled_at = ?, content_hash = ?
                WHERE url = ?
                """,
                (normalized, content_hash, url),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"unknown source URL: {url}")

    def due_sources(self, *, now: datetime) -> tuple[WebSource, ...]:
        current = _as_utc(now)
        rows = self._connection.execute(
            "SELECT * FROM source_registry WHERE status = 'active' ORDER BY url"
        ).fetchall()
        due: list[WebSource] = []
        for row in rows:
            last_raw = row["last_crawled_at"]
            last = datetime.fromisoformat(last_raw) if last_raw else None
            interval = timedelta(hours=int(row["crawl_interval_hours"]))
            if last is None or _as_utc(last) + interval <= current:
                due.append(
                    WebSource(
                        url=row["url"],
                        source_type=row["source_type"],
                        domain=row["domain"],
                        crawl_interval_hours=int(row["crawl_interval_hours"]),
                        status=row["status"],
                        last_crawled_at=last_raw,
                        content_hash=row["content_hash"],
                    )
                )
        return tuple(due)

    def close(self) -> None:
        self._connection.close()

    # --- Jobs CRUD ------------------------------------------------------------

    def list_jobs(
        self,
        *,
        company_type: str | None = None,
        company: str | None = None,
        user_id: str | None = None,
        limit: int = 200,
    ) -> tuple[sqlite3.Row, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if company_type:
            clauses.append("organization_type = ?")
            params.append(company_type)
        if company:
            clauses.append("company_name = ?")
            params.append(company)
        if user_id is None:
            clauses.append("owner_user_id IS NULL")
        else:
            clauses.append("(owner_user_id IS NULL OR owner_user_id = ?)")
            params.append(user_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 1000)))
        rows = self._connection.execute(
            f"""
            SELECT * FROM job_records {where}
            ORDER BY verified_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return tuple(rows)

    def get_job(self, job_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM job_records WHERE id = ?", (job_id,)
        ).fetchone()

    def search_job_records(self, query: str, *, limit: int = 10) -> tuple[SearchHit, ...]:
        """Search normalized job objects before falling back to document retrieval."""
        terms = _structured_query_terms(query)
        if not terms:
            return ()
        rows = self._connection.execute(
            """
            SELECT * FROM job_records
            WHERE owner_user_id IS NULL AND status <> 'expired'
            ORDER BY verified_at DESC
            LIMIT 500
            """
        ).fetchall()
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            searchable = " ".join(
                str(row[field] or "")
                for field in (
                    "company_name",
                    "role_title",
                    "role_family",
                    "organization_type",
                    "locations_json",
                    "job_description",
                    "requirements",
                )
            ).casefold()
            matched = sum(1 for term in terms if term in searchable)
            if matched:
                scored.append((matched / len(terms), row))
        scored.sort(key=lambda item: (-item[0], str(item[1]["id"])))
        return tuple(
            SearchHit(
                chunk_id=str(row["id"]),
                document_id=str(row["id"]),
                title=f"{row['company_name']}｜{row['role_title']}",
                heading="结构化岗位记录",
                content=(
                    f"公司：{row['company_name']}\n岗位：{row['role_title']}\n"
                    f"地点：{'、'.join(json.loads(row['locations_json']))}\n"
                    f"截止：{row['deadline'] or '未公开'}\n"
                    f"岗位描述：{row['job_description']}\n任职要求：{row['requirements']}"
                ),
                source_uri=str(row["source_url"]),
                source_type=f"job_source_{row['source_level']}",
                domain="job_opportunity",
                score=score,
                metadata={
                    "company_name": row["company_name"],
                    "role_title": row["role_title"],
                    "organization_type": row["organization_type"],
                    "locations": json.loads(row["locations_json"]),
                    "deadline": row["deadline"],
                    "apply_url": row["apply_url"],
                    "verified_at": row["verified_at"],
                    "status": row["status"],
                },
                evidence_id=f"job-record:{row['id']}",
                evidence_kind=EvidenceKind.API_OBJECT,
                channels=("structured",),
                knowledge_origin=KnowledgeOrigin.SYSTEM_WEB,
            )
            for score, row in scored[: max(1, min(limit, 100))]
        )

    def upsert_job(self, job: dict[str, object]) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO job_records
            (id, company_name, role_title, role_family, recruiting_type,
             organization_type, employment_type, locations_json, deadline,
             apply_url, source_url, source_level, source_name, posted_at,
             verified_at, job_description, requirements, status,
             knowledge_origin, owner_user_id)
            VALUES (:id, :company_name, :role_title, :role_family,
                    :recruiting_type, :organization_type, :employment_type,
                    :locations_json, :deadline, :apply_url, :source_url,
                    :source_level, :source_name, :posted_at, :verified_at,
                    :job_description, :requirements, :status,
                    COALESCE(:knowledge_origin, 'system_curated'),
                    :owner_user_id)
            """,
            job,
        )

    # --- User document metadata -----------------------------------------------

    def list_user_documents(self, user_id: str) -> tuple[sqlite3.Row, ...]:
        return tuple(
            self._connection.execute(
                "SELECT * FROM user_documents WHERE owner_user_id = ? ORDER BY uploaded_at DESC",
                (user_id,),
            ).fetchall()
        )

    def upsert_user_document(self, doc: dict[str, object]) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO user_documents
            (id, title, category, file_format, size_text, uploaded_at,
             status, retrieval_enabled, owner_user_id)
            VALUES (:id, :title, :category, :file_format, :size_text,
                    :uploaded_at, :status, :retrieval_enabled, :owner_user_id)
            """,
            doc,
        )

    def delete_user_document(self, doc_id: str, user_id: str) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM user_documents WHERE id = ? AND owner_user_id = ?",
            (doc_id, user_id),
        )
        return cursor.rowcount > 0


def _append_access_filters(
    filters: list[str],
    params: list[object],
    *,
    user_id: str | None,
    origins: frozenset[KnowledgeOrigin] | None,
    prefix: str = "",
) -> None:
    owner_column = f"{prefix}owner_user_id"
    origin_column = f"{prefix}knowledge_origin"
    if user_id is None:
        filters.append(f"{owner_column} IS NULL")
    else:
        filters.append(f"({owner_column} IS NULL OR {owner_column} = ?)")
        params.append(user_id)
    if origins:
        ordered = sorted(origins, key=lambda item: item.value)
        placeholders = ",".join("?" for _ in ordered)
        filters.append(f"{origin_column} IN ({placeholders})")
        params.extend(origin.value for origin in ordered)


def _fts_query(query: str) -> str:
    ascii_terms = re.findall(r"[A-Za-z][A-Za-z0-9_.+-]{2,}", query)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    chinese_terms: list[str] = []
    for run in chinese_runs:
        if len(run) <= 4:
            chinese_terms.append(run)
        else:
            chinese_terms.extend(run[index : index + 3] for index in range(len(run) - 2))
    terms = list(dict.fromkeys(ascii_terms + chinese_terms))
    return " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _canonical_phrase(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _structured_query_terms(query: str) -> tuple[str, ...]:
    stop_terms = {
        "哪些",
        "什么",
        "最近",
        "目前",
        "现在",
        "岗位",
        "职位",
        "招聘",
        "还有",
        "开放",
    }
    ascii_terms = [term.casefold() for term in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]+", query)]
    chinese_terms: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        chinese_terms.extend(run[index : index + 2] for index in range(len(run) - 1))
        chinese_terms.extend(run[index : index + 4] for index in range(max(0, len(run) - 3)))
    return tuple(
        term for term in dict.fromkeys((*ascii_terms, *chinese_terms)) if term not in stop_terms
    )


def _graph_node_id(node_type: str, identity: str) -> str:
    digest = hashlib.sha256(f"{node_type}:{identity}".encode()).hexdigest()[:24]
    return f"graph-node-{digest}"


def _graph_edge_id(source: str, predicate: str, target: str) -> str:
    digest = hashlib.sha256(f"{source}:{predicate}:{target}".encode()).hexdigest()[:24]
    return f"graph-edge-{digest}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
