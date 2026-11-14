from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from careerpilot.exploration.models import (
    EVIDENCE_KINDS,
    NODE_TYPES,
    RELATION_TYPES,
    ExplorationProjection,
)


class ExplorationService:
    """Owner-scoped career exploration graph built from source-backed product events."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS exploration_threads (
                owner_id TEXT NOT NULL, id TEXT NOT NULL,
                seed_text TEXT NOT NULL, working_question TEXT NOT NULL,
                status TEXT NOT NULL, focus_node_id TEXT,
                source_direction_id TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS exploration_direction_idx
                ON exploration_threads(owner_id, source_direction_id)
                WHERE source_direction_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS exploration_threads_owner_idx
                ON exploration_threads(owner_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS career_nodes (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, thread_id TEXT NOT NULL,
                node_type TEXT NOT NULL, raw_label TEXT NOT NULL,
                canonical_label TEXT NOT NULL, status TEXT NOT NULL,
                source_reference TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS career_node_identity_idx
                ON career_nodes(owner_id, thread_id, node_type, canonical_label);
            CREATE INDEX IF NOT EXISTS career_nodes_thread_idx
                ON career_nodes(owner_id, thread_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS career_edges (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, thread_id TEXT NOT NULL,
                from_node_id TEXT NOT NULL, to_node_id TEXT NOT NULL,
                relation_type TEXT NOT NULL, source_reference TEXT,
                status TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS career_edge_identity_idx
                ON career_edges(
                    owner_id, thread_id, from_node_id, to_node_id, relation_type
                );

            CREATE TABLE IF NOT EXISTS career_evidence (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, thread_id TEXT NOT NULL,
                node_id TEXT, kind TEXT NOT NULL, source_type TEXT NOT NULL,
                source_reference TEXT NOT NULL, excerpt TEXT NOT NULL,
                confidence REAL NOT NULL, confirmation_status TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS career_evidence_identity_idx
                ON career_evidence(
                    owner_id, thread_id, node_id, kind, source_reference
                );
            CREATE INDEX IF NOT EXISTS career_evidence_thread_idx
                ON career_evidence(owner_id, thread_id, created_at DESC);
            """
        )
        self._connection.commit()

    def create_thread(
        self,
        owner_id: str,
        *,
        seed_text: str,
        working_question: str,
        source_direction_id: str | None = None,
    ) -> dict[str, object]:
        if source_direction_id is not None:
            existing = self._connection.execute(
                """SELECT * FROM exploration_threads
                WHERE owner_id = ? AND source_direction_id = ?""",
                (owner_id, source_direction_id),
            ).fetchone()
            if existing is not None:
                return self._decode(existing)
        now = datetime.now(UTC).isoformat()
        thread_id = f"explore-{uuid.uuid4().hex[:12]}"
        with self._connection:
            self._connection.execute(
                """INSERT INTO exploration_threads
                (owner_id,id,seed_text,working_question,status,focus_node_id,
                 source_direction_id,created_at,updated_at)
                VALUES (?,?,?,?, 'active', NULL, ?,?,?)""",
                (
                    owner_id,
                    thread_id,
                    self._clean(seed_text),
                    self._clean(working_question),
                    source_direction_id,
                    now,
                    now,
                ),
            )
        return self._require_thread(owner_id, thread_id)

    def upsert_node(
        self,
        owner_id: str,
        *,
        thread_id: str,
        node_type: str,
        raw_label: str,
        canonical_label: str | None = None,
        source_reference: str | None = None,
        status: str = "active",
    ) -> dict[str, object]:
        if node_type not in NODE_TYPES:
            raise ValueError(f"unsupported career node type: {node_type}")
        self._require_thread(owner_id, thread_id)
        raw = self._clean(raw_label)
        canonical = self._clean(canonical_label or raw)
        existing = self._connection.execute(
            """SELECT * FROM career_nodes
            WHERE owner_id = ? AND thread_id = ? AND node_type = ?
              AND canonical_label = ?""",
            (owner_id, thread_id, node_type, canonical),
        ).fetchone()
        if existing is not None:
            return self._decode(existing)
        now = datetime.now(UTC).isoformat()
        node_id = f"career-node-{uuid.uuid4().hex[:12]}"
        with self._connection:
            self._connection.execute(
                """INSERT INTO career_nodes
                (owner_id,id,thread_id,node_type,raw_label,canonical_label,status,
                 source_reference,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    owner_id,
                    node_id,
                    thread_id,
                    node_type,
                    raw,
                    canonical,
                    status,
                    source_reference,
                    now,
                    now,
                ),
            )
            self._connection.execute(
                """UPDATE exploration_threads
                SET focus_node_id = COALESCE(focus_node_id, ?), updated_at = ?
                WHERE owner_id = ? AND id = ?""",
                (node_id, now, owner_id, thread_id),
            )
        return self._require_node(owner_id, node_id)

    def connect_nodes(
        self,
        owner_id: str,
        *,
        thread_id: str,
        from_node_id: str,
        to_node_id: str,
        relation_type: str,
        source_reference: str | None = None,
    ) -> dict[str, object]:
        if relation_type not in RELATION_TYPES:
            raise ValueError(f"unsupported career relation type: {relation_type}")
        for node_id in (from_node_id, to_node_id):
            node = self._require_node(owner_id, node_id)
            if node["thread_id"] != thread_id:
                raise ValueError("career edge nodes must belong to the same thread")
        existing = self._connection.execute(
            """SELECT * FROM career_edges
            WHERE owner_id = ? AND thread_id = ? AND from_node_id = ?
              AND to_node_id = ? AND relation_type = ?""",
            (owner_id, thread_id, from_node_id, to_node_id, relation_type),
        ).fetchone()
        if existing is not None:
            return self._decode(existing)
        edge_id = f"career-edge-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        with self._connection:
            self._connection.execute(
                """INSERT INTO career_edges
                (owner_id,id,thread_id,from_node_id,to_node_id,relation_type,
                 source_reference,status,created_at)
                VALUES (?,?,?,?,?,?,?,'active',?)""",
                (
                    owner_id,
                    edge_id,
                    thread_id,
                    from_node_id,
                    to_node_id,
                    relation_type,
                    source_reference,
                    now,
                ),
            )
        row = self._connection.execute(
            "SELECT * FROM career_edges WHERE owner_id = ? AND id = ?",
            (owner_id, edge_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def add_evidence(
        self,
        owner_id: str,
        *,
        thread_id: str,
        node_id: str | None,
        kind: str,
        source_type: str,
        source_reference: str,
        excerpt: str,
        confidence: float,
        confirmation_status: str,
    ) -> dict[str, object]:
        if kind not in EVIDENCE_KINDS:
            raise ValueError(f"unsupported career evidence kind: {kind}")
        self._require_thread(owner_id, thread_id)
        if node_id is not None:
            node = self._require_node(owner_id, node_id)
            if node["thread_id"] != thread_id:
                raise ValueError("career evidence node must belong to its thread")
        existing = self._connection.execute(
            """SELECT * FROM career_evidence
            WHERE owner_id = ? AND thread_id = ? AND node_id IS ?
              AND kind = ? AND source_reference = ?""",
            (owner_id, thread_id, node_id, kind, source_reference),
        ).fetchone()
        if existing is not None:
            return self._decode(existing)
        now = datetime.now(UTC).isoformat()
        evidence_id = f"career-evidence-{uuid.uuid4().hex[:12]}"
        with self._connection:
            self._connection.execute(
                """INSERT INTO career_evidence
                (owner_id,id,thread_id,node_id,kind,source_type,source_reference,
                 excerpt,confidence,confirmation_status,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,'active',?,?)""",
                (
                    owner_id,
                    evidence_id,
                    thread_id,
                    node_id,
                    kind,
                    source_type,
                    source_reference,
                    self._clean(excerpt),
                    max(0.0, min(1.0, confidence)),
                    confirmation_status,
                    now,
                    now,
                ),
            )
        row = self._connection.execute(
            "SELECT * FROM career_evidence WHERE owner_id = ? AND id = ?",
            (owner_id, evidence_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def project_compass_batch(
        self, owner_id: str, batch_id: str
    ) -> ExplorationProjection | None:
        batch = self._connection.execute(
            """SELECT b.*, d.label AS direction_label
            FROM compass_update_batches b
            LEFT JOIN directions d ON d.owner_id = b.owner_id AND d.id = b.direction_id
            WHERE b.owner_id = ? AND b.id = ? AND b.status = 'committed'""",
            (owner_id, batch_id),
        ).fetchone()
        if batch is None or batch["direction_id"] is None:
            return None
        label = self._clean(str(batch["direction_label"] or "待确认方向"))
        thread = self.create_thread(
            owner_id,
            seed_text=label,
            working_question=f"“{label}”下面，哪种具体工作和组织环境更适合你？",
            source_direction_id=str(batch["direction_id"]),
        )
        thread_id = str(thread["id"])
        direction_node = self.upsert_node(
            owner_id,
            thread_id=thread_id,
            node_type=self._infer_direction_type(label),
            raw_label=label,
            source_reference=f"direction:{batch['direction_id']}",
        )
        focus_node = direction_node
        branch = None
        if batch["branch_id"] is not None:
            branch = self._connection.execute(
                """SELECT * FROM direction_branches
                WHERE owner_id = ? AND id = ? AND status != 'archived'""",
                (owner_id, batch["branch_id"]),
            ).fetchone()
        if branch is not None:
            previous = direction_node
            for node_type, field, relation in (
                ("role", "role", "specializes_to"),
                ("organization", "company", "contextualized_as"),
                ("business_context", "business", "contains"),
                ("location_context", "location", "contextualized_as"),
            ):
                value = " ".join(str(branch[field]).split())
                if not value or (node_type == "role" and value == label):
                    continue
                node = self.upsert_node(
                    owner_id,
                    thread_id=thread_id,
                    node_type=node_type,
                    raw_label=value,
                    source_reference=f"branch:{branch['id']}:{field}",
                )
                self.connect_nodes(
                    owner_id,
                    thread_id=thread_id,
                    from_node_id=str(previous["id"]),
                    to_node_id=str(node["id"]),
                    relation_type=relation,
                    source_reference=f"batch:{batch_id}",
                )
                previous = node
                if node_type == "role":
                    focus_node = node
        self.add_evidence(
            owner_id,
            thread_id=thread_id,
            node_id=str(focus_node["id"]),
            kind="support",
            source_type="user_turn",
            source_reference=f"turn:{batch['run_id']}",
            excerpt=str(batch["source_quote"]),
            confidence=1.0,
            confirmation_status="confirmed",
        )
        items = self._connection.execute(
            """SELECT kind,value FROM compass_update_items
            WHERE owner_id = ? AND batch_id = ? AND status != 'undone'""",
            (owner_id, batch_id),
        ).fetchall()
        for index, item in enumerate(row for row in items if row["kind"] == "constraint"):
            self.add_evidence(
                owner_id,
                thread_id=thread_id,
                node_id=str(focus_node["id"]),
                kind="unknown",
                source_type="user_constraint",
                source_reference=f"batch:{batch_id}:constraint:{index}",
                excerpt=f"需要验证现实约束：{item['value']}",
                confidence=1.0,
                confirmation_status="confirmed",
            )
        with self._connection:
            self._connection.execute(
                """UPDATE exploration_threads SET focus_node_id = ?, updated_at = ?
                WHERE owner_id = ? AND id = ?""",
                (
                    focus_node["id"],
                    datetime.now(UTC).isoformat(),
                    owner_id,
                    thread_id,
                ),
            )
        return ExplorationProjection(thread_id, str(focus_node["id"]))

    def list_views(self, owner_id: str) -> list[dict[str, object]]:
        threads = self._connection.execute(
            """SELECT * FROM exploration_threads
            WHERE owner_id = ? AND status != 'archived'
            ORDER BY updated_at DESC, id""",
            (owner_id,),
        ).fetchall()
        return [self._view(owner_id, row) for row in threads]

    def _view(self, owner_id: str, thread: sqlite3.Row) -> dict[str, object]:
        thread_id = str(thread["id"])
        nodes = self._connection.execute(
            """SELECT * FROM career_nodes WHERE owner_id = ? AND thread_id = ?
            AND status != 'archived' ORDER BY created_at, id""",
            (owner_id, thread_id),
        ).fetchall()
        edges = self._connection.execute(
            """SELECT * FROM career_edges WHERE owner_id = ? AND thread_id = ?
            AND status != 'archived' ORDER BY created_at, id""",
            (owner_id, thread_id),
        ).fetchall()
        evidence = self._connection.execute(
            """SELECT * FROM career_evidence WHERE owner_id = ? AND thread_id = ?
            AND status != 'archived' ORDER BY created_at, id""",
            (owner_id, thread_id),
        ).fetchall()
        by_kind = {
            kind: [self._decode(row) for row in evidence if row["kind"] == kind]
            for kind in EVIDENCE_KINDS
        }
        focus = next(
            (
                self._decode(row)
                for row in nodes
                if row["id"] == thread["focus_node_id"]
            ),
            None,
        )
        return {
            "thread": self._decode(thread),
            "focus": focus,
            "nodes": [self._decode(row) for row in nodes],
            "edges": [self._decode(row) for row in edges],
            "supporting_evidence": by_kind["support"],
            "counter_evidence": by_kind["counter"],
            "unknowns": by_kind["unknown"],
        }

    def _require_thread(self, owner_id: str, thread_id: str) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT * FROM exploration_threads WHERE owner_id = ? AND id = ?",
            (owner_id, thread_id),
        ).fetchone()
        if row is None:
            raise LookupError(thread_id)
        return self._decode(row)

    def _require_node(self, owner_id: str, node_id: str) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT * FROM career_nodes WHERE owner_id = ? AND id = ?",
            (owner_id, node_id),
        ).fetchone()
        if row is None:
            raise LookupError(node_id)
        return self._decode(row)

    @staticmethod
    def _infer_direction_type(label: str) -> str:
        broad = {"开发", "研发", "产品", "设计", "运营", "销售", "咨询"}
        return "role_family" if label in broad else "role"

    @staticmethod
    def _clean(value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("career exploration text must not be empty")
        return cleaned

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, object]:
        return {key: row[key] for key in row.keys() if key != "owner_id"}
