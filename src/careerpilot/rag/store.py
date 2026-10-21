import json
import math
import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from careerpilot.rag.embeddings import EmbeddingProvider
from careerpilot.rag.evidence import build_evidence_units
from careerpilot.rag.models import (
    DocumentChunk,
    EvidenceKind,
    EvidenceUnit,
    SearchHit,
    SourceDocument,
    WebSource,
)


class SqliteRagStore:
    """Compact evidence store with sparse, optional dense, and local graph retrieval."""

    def __init__(self, path: Path, *, embedder: EmbeddingProvider | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self._embedder = embedder
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
                fetched_at TEXT
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
                metadata_json TEXT NOT NULL
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
                object TEXT
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
            CREATE TABLE IF NOT EXISTS source_registry (
                url TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                crawl_interval_hours INTEGER NOT NULL,
                status TEXT NOT NULL,
                last_crawled_at TEXT,
                content_hash TEXT
            );
            """
        )

    def upsert(
        self,
        document: SourceDocument,
        chunks: tuple[DocumentChunk, ...],
        evidence_units: tuple[EvidenceUnit, ...] | None = None,
    ) -> None:
        units = evidence_units or build_evidence_units(document, chunks)
        vectors = self._embed_units(units)
        with self._connection:
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
                """
                INSERT OR REPLACE INTO documents
                (id, title, source_uri, source_type, domain, text, metadata_json,
                 published_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            for chunk in chunks:
                self._connection.execute(
                    """
                    INSERT INTO chunks
                    (id, document_id, ordinal, title, heading, content, source_uri,
                     source_type, domain, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
            for unit, vector in zip(units, vectors, strict=True):
                self._insert_evidence(unit, vector)

    def _embed_units(self, units: tuple[EvidenceUnit, ...]) -> list[list[float] | None]:
        if self._embedder is None or not units:
            return [None] * len(units)
        try:
            vectors = self._embedder.embed_documents([unit.embedding_text for unit in units])
        except Exception:
            return [None] * len(units)
        if len(vectors) != len(units):
            return [None] * len(units)
        return [list(vector) for vector in vectors]

    def _insert_evidence(self, unit: EvidenceUnit, vector: list[float] | None) -> None:
        self._connection.execute(
            """
            INSERT INTO evidence_units
            (id, kind, document_id, parent_id, title, embedding_text, source_uri,
             source_type, domain, metadata_json, vector_json, subject, predicate, object)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        limit: int = 5,
    ) -> tuple[SearchHit, ...]:
        return self.search_sparse(query, domain=domain, limit=limit)

    def search_sparse(
        self,
        query: str,
        *,
        domain: str | None = None,
        kinds: frozenset[EvidenceKind] | None = None,
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
        domain: str | None = None,
        kinds: frozenset[EvidenceKind] | None = None,
        limit: int = 5,
    ) -> tuple[SearchHit, ...]:
        if self._embedder is None or not query.strip():
            return ()
        try:
            query_vector = self._embedder.embed_query(query)
        except Exception:
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

    def neighbors(
        self,
        evidence_ids: Iterable[str | None],
        *,
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
        rows = self._connection.execute(
            f"""
            SELECT * FROM evidence_units
            WHERE kind = ?
              AND (subject IN ({node_placeholders}) OR object IN ({node_placeholders}))
              AND id NOT IN ({placeholders})
              AND parent_id IS NOT NULL
              AND source_uri <> ''
            ORDER BY id
            LIMIT ?
            """,
            (
                EvidenceKind.KG_TRIPLE.value,
                *nodes,
                *nodes,
                *seed_ids,
                max(1, min(limit, 100)),
            ),
        ).fetchall()
        return tuple(self._row_to_hit(row, score=0.0, channels=("graph",)) for row in rows)

    def _row_to_hit(
        self,
        row: sqlite3.Row,
        *,
        score: float,
        channels: tuple[str, ...],
    ) -> SearchHit:
        metadata = json.loads(row["metadata_json"])
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
        )

    def count_documents(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM documents").fetchone()
        return int(row["count"])

    def count_chunks(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()
        return int(row["count"])

    def count_evidence(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM evidence_units").fetchone()
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


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
