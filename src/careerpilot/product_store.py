from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path


class ProductStore:
    """Owner-scoped product state used by the web experience.

    Every query includes owner_id. Public career knowledge remains in the RAG store.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS hypotheses (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, statement TEXT NOT NULL,
                confidence TEXT NOT NULL, status TEXT NOT NULL, evidence_json TEXT NOT NULL,
                section TEXT NOT NULL, PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS journey_tasks (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
                due TEXT NOT NULL, state TEXT NOT NULL, related TEXT NOT NULL,
                hypothesis_id TEXT, why TEXT NOT NULL, reflection TEXT,
                PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS memories (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, type TEXT NOT NULL,
                content TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
                compass_section TEXT, PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS dreaming_insights (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, date TEXT NOT NULL,
                title TEXT NOT NULL, summary TEXT NOT NULL, status TEXT NOT NULL,
                details_json TEXT NOT NULL, PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS conversations (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
                role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS direction_signals (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, source_run_id TEXT NOT NULL,
                label TEXT NOT NULL, explicitness TEXT NOT NULL, source_quote TEXT NOT NULL,
                reason TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL,
                conversation_id TEXT, signal_kind TEXT NOT NULL DEFAULT 'direction',
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, source_run_id)
            );
            CREATE TABLE IF NOT EXISTS directions (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, label TEXT NOT NULL,
                status TEXT NOT NULL, source_signal_id TEXT NOT NULL,
                source_kind TEXT NOT NULL, source_quote TEXT NOT NULL,
                reason TEXT NOT NULL, confidence REAL NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, source_signal_id)
            );
            CREATE TABLE IF NOT EXISTS journeys (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, direction_id TEXT NOT NULL,
                title TEXT NOT NULL, status TEXT NOT NULL, why TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, direction_id)
            );
            CREATE TABLE IF NOT EXISTS journey_branches (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, journey_id TEXT NOT NULL,
                compass_branch_id TEXT, kind TEXT NOT NULL, title TEXT NOT NULL,
                status TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 0,
                rationale TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS compass_update_batches (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, run_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL, direction_id TEXT, branch_id TEXT,
                source_quote TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, undone_at TEXT,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, run_id)
            );
            CREATE TABLE IF NOT EXISTS compass_update_items (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, batch_id TEXT NOT NULL,
                kind TEXT NOT NULL, value TEXT NOT NULL, explicitness TEXT NOT NULL,
                status TEXT NOT NULL, source_quote TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS direction_branches (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, direction_id TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '', business TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '',
                normalized_key TEXT NOT NULL, status TEXT NOT NULL,
                source_batch_id TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, direction_id, normalized_key)
            );
            CREATE TABLE IF NOT EXISTS career_profile_items (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, category TEXT NOT NULL,
                value TEXT NOT NULL, explicitness TEXT NOT NULL, status TEXT NOT NULL,
                source_batch_id TEXT NOT NULL, source_quote TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS direction_evidence (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, direction_id TEXT NOT NULL,
                branch_id TEXT, kind TEXT NOT NULL, content TEXT NOT NULL,
                status TEXT NOT NULL, source_kind TEXT NOT NULL, source_reference TEXT,
                source_quote TEXT, created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS knowledge_collection_jobs (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, direction_id TEXT NOT NULL,
                journey_id TEXT, purpose TEXT NOT NULL, query TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                result_count INTEGER NOT NULL DEFAULT 0, last_error TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, direction_id, purpose)
            );
            CREATE TABLE IF NOT EXISTS contextual_collection_jobs (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, direction_id TEXT NOT NULL,
                compass_branch_id TEXT, journey_id TEXT, journey_branch_id TEXT,
                purpose TEXT NOT NULL, query TEXT NOT NULL, normalized_query_key TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                result_count INTEGER NOT NULL DEFAULT 0, last_error TEXT,
                last_verified_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, normalized_query_key)
            );
            CREATE TABLE IF NOT EXISTS journey_future_letters (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, journey_id TEXT NOT NULL,
                message TEXT NOT NULL, paths_json TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE TABLE IF NOT EXISTS journey_future_takeaways (
                owner_id TEXT NOT NULL, letter_id TEXT NOT NULL, journey_id TEXT NOT NULL,
                path_kind TEXT NOT NULL, question TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, letter_id)
            );
            CREATE INDEX IF NOT EXISTS hypotheses_owner_idx ON hypotheses(owner_id);
            CREATE INDEX IF NOT EXISTS journey_owner_idx ON journey_tasks(owner_id);
            CREATE INDEX IF NOT EXISTS memories_owner_idx ON memories(owner_id);
            CREATE INDEX IF NOT EXISTS dreaming_owner_idx ON dreaming_insights(owner_id);
            CREATE INDEX IF NOT EXISTS conversations_owner_updated_idx
                ON conversations(owner_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS conversation_messages_owner_idx
                ON conversation_messages(owner_id, conversation_id, sequence);
            CREATE INDEX IF NOT EXISTS direction_signals_owner_status_idx
                ON direction_signals(owner_id, status, updated_at DESC);
            CREATE INDEX IF NOT EXISTS directions_owner_status_idx
                ON directions(owner_id, status, updated_at DESC);
            CREATE INDEX IF NOT EXISTS journeys_owner_updated_idx
                ON journeys(owner_id, updated_at DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS journey_common_branch_idx
                ON journey_branches(owner_id, journey_id) WHERE kind = 'common';
            CREATE UNIQUE INDEX IF NOT EXISTS journey_target_branch_idx
                ON journey_branches(owner_id, journey_id, compass_branch_id)
                WHERE kind = 'target' AND compass_branch_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS collection_jobs_owner_status_idx
                ON knowledge_collection_jobs(owner_id, status, updated_at DESC);
            CREATE INDEX IF NOT EXISTS contextual_jobs_owner_status_idx
                ON contextual_collection_jobs(owner_id, status, updated_at DESC);
            CREATE INDEX IF NOT EXISTS compass_batches_owner_created_idx
                ON compass_update_batches(owner_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS direction_branches_owner_direction_idx
                ON direction_branches(owner_id, direction_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS future_letters_owner_journey_idx
                ON journey_future_letters(owner_id, journey_id, created_at DESC);
            """
        )
        journey_columns = {
            str(row["name"])
            for row in self._connection.execute("PRAGMA table_info(journey_tasks)").fetchall()
        }
        if "idea_id" not in journey_columns:
            self._connection.execute("ALTER TABLE journey_tasks ADD COLUMN idea_id TEXT")
        journey_column_definitions = {
            "start_at": "TEXT",
            "end_at": "TEXT",
            "reminder_minutes": "INTEGER",
            "meeting_url": "TEXT",
            "notes": "TEXT",
            "created_via": "TEXT NOT NULL DEFAULT 'journey'",
            "source_reference": "TEXT",
            "journey_id": "TEXT",
            "direction_id": "TEXT",
            "step_kind": "TEXT",
            "collection_job_id": "TEXT",
            "journey_branch_id": "TEXT",
            "scope": "TEXT NOT NULL DEFAULT 'common'",
            "target_job_id": "TEXT",
        }
        for column, definition in journey_column_definitions.items():
            if column not in journey_columns:
                self._connection.execute(
                    f"ALTER TABLE journey_tasks ADD COLUMN {column} {definition}"
                )
        collection_columns = {
            str(row["name"])
            for row in self._connection.execute(
                "PRAGMA table_info(knowledge_collection_jobs)"
            ).fetchall()
        }
        if "result_count" not in collection_columns:
            self._connection.execute(
                "ALTER TABLE knowledge_collection_jobs "
                "ADD COLUMN result_count INTEGER NOT NULL DEFAULT 0"
            )
        if "last_error" not in collection_columns:
            self._connection.execute(
                "ALTER TABLE knowledge_collection_jobs ADD COLUMN last_error TEXT"
            )
        signal_columns = {
            str(row["name"])
            for row in self._connection.execute("PRAGMA table_info(direction_signals)").fetchall()
        }
        for column, definition in {
            "conversation_id": "TEXT",
            "signal_kind": "TEXT NOT NULL DEFAULT 'direction'",
            "context_json": "TEXT NOT NULL DEFAULT '{}'",
        }.items():
            if column not in signal_columns:
                self._connection.execute(
                    f"ALTER TABLE direction_signals ADD COLUMN {column} {definition}"
                )
        self._connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS journey_source_reference_idx
            ON journey_tasks(owner_id, source_reference)
            WHERE source_reference IS NOT NULL"""
        )
        self._connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS journey_step_kind_idx
            ON journey_tasks(owner_id, journey_id, step_kind)
            WHERE journey_id IS NOT NULL AND step_kind IS NOT NULL"""
        )
        self._connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS direction_evidence_source_idx
            ON direction_evidence(owner_id, source_kind, source_reference)
            WHERE source_reference IS NOT NULL"""
        )
        self._connection.commit()
        self._repair_unbound_explicit_targets()
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def dashboard(self, owner_id: str) -> dict[str, object]:
        directions = self.list_directions(owner_id)
        return {
            "hypotheses": self._rows("hypotheses", owner_id, "id"),
            "journey": self._rows("journey_tasks", owner_id, "rowid"),
            "memories": self._rows("memories", owner_id, "rowid"),
            "dreaming": self._rows("dreaming_insights", owner_id, "rowid DESC"),
            "directions": directions,
            "journeys": self._rows("journeys", owner_id, "updated_at DESC"),
            "collection_jobs": self.list_collection_jobs(owner_id),
            "direction_signals": self._rows(
                "direction_signals", owner_id, "updated_at DESC"
            ),
            "compass_update_batches": self.list_compass_update_batches(owner_id),
            "direction_branches": self._rows(
                "direction_branches", owner_id, "updated_at DESC"
            ),
            "career_profile": self._rows(
                "career_profile_items", owner_id, "updated_at DESC"
            ),
            "direction_evidence": self._rows(
                "direction_evidence", owner_id, "created_at DESC"
            ),
            "direction_summaries": [
                {
                    "direction_id": item["id"],
                    "reason": item["reason"],
                    "unknown_question": "这个方向的真实工作方式是否适合你？",
                    "recent_change": item["source_quote"],
                    "next_validation": "查看一个真实岗位并记录最想进一步确认的问题",
                    "updated_at": item["updated_at"],
                }
                for item in directions
            ],
            "journey_branches": self.list_journey_branches(owner_id),
        }

    def record_direction_signal(
        self,
        owner_id: str,
        *,
        source_run_id: str,
        label: str,
        explicitness: str,
        source_quote: str,
        reason: str,
        confidence: float,
        conversation_id: str | None = None,
        signal_kind: str = "direction",
        context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if explicitness not in {"explicit", "implicit"}:
            raise ValueError("only explicit or implicit signals can be persisted")
        existing = self._connection.execute(
            "SELECT * FROM direction_signals WHERE owner_id = ? AND source_run_id = ?",
            (owner_id, source_run_id),
        ).fetchone()
        if existing is not None:
            return self._decode(existing)
        now = datetime.now(UTC).isoformat()
        signal_id = f"signal-{uuid.uuid4().hex[:12]}"
        status = "accepted" if explicitness == "explicit" else "pending"
        with self._connection:
            self._connection.execute(
                """INSERT INTO direction_signals
                (owner_id,id,source_run_id,label,explicitness,source_quote,reason,
                 confidence,status,conversation_id,signal_kind,context_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    owner_id,
                    signal_id,
                    source_run_id,
                    " ".join(label.split()),
                    explicitness,
                    source_quote,
                    reason,
                    confidence,
                    status,
                    conversation_id,
                    signal_kind,
                    json.dumps(context or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            if explicitness == "explicit" and signal_kind == "direction":
                self._create_direction_from_signal(owner_id, signal_id, now)
        row = self._connection.execute(
            "SELECT * FROM direction_signals WHERE owner_id = ? AND id = ?",
            (owner_id, signal_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def commit_compass_update(
        self,
        owner_id: str,
        *,
        run_id: str,
        conversation_id: str,
        label: str | None,
        explicitness: str,
        source_quote: str,
        reason: str,
        confidence: float,
        signal_kind: str = "direction",
        company: str | None = None,
        business: str | None = None,
        role: str | None = None,
        location: str | None = None,
        constraints: tuple[str, ...] = (),
    ) -> dict[str, object]:
        existing = self._connection.execute(
            "SELECT id FROM compass_update_batches WHERE owner_id = ? AND run_id = ?",
            (owner_id, run_id),
        ).fetchone()
        if existing is not None:
            return self._compass_batch_payload(owner_id, str(existing["id"]))

        context = {
            "company": company,
            "business": business,
            "role": role,
            "location": location,
            "constraints": list(constraints),
        }
        signal = self.record_direction_signal(
            owner_id,
            source_run_id=run_id,
            label=label or role or company or business or "待确认目标",
            explicitness=explicitness,
            source_quote=source_quote,
            reason=reason,
            confidence=confidence,
            conversation_id=conversation_id,
            signal_kind=signal_kind,
            context=context,
        )
        direction_id: str | None = None
        if signal_kind == "direction":
            direction = self._connection.execute(
                "SELECT id FROM directions WHERE owner_id = ? AND source_signal_id = ?",
                (owner_id, signal["id"]),
            ).fetchone()
            if direction is None and label:
                direction = self._connection.execute(
                    """SELECT id FROM directions
                    WHERE owner_id = ? AND status != 'archived'
                      AND lower(trim(label)) = lower(trim(?))
                    ORDER BY updated_at DESC LIMIT 1""",
                    (owner_id, label),
                ).fetchone()
            if direction is not None:
                direction_id = str(direction["id"])
        else:
            bound = self._connection.execute(
                """SELECT d.id FROM directions d
                JOIN direction_signals s ON s.owner_id = d.owner_id
                    AND s.id = d.source_signal_id
                WHERE d.owner_id = ? AND s.conversation_id = ?
                ORDER BY s.updated_at DESC LIMIT 1""",
                (owner_id, conversation_id),
            ).fetchone()
            if bound is not None:
                direction_id = str(bound["id"])
            else:
                direction_id = self._find_matching_direction(
                    owner_id, role, label
                )

        now = datetime.now(UTC).isoformat()
        batch_id = f"compass-{uuid.uuid4().hex[:12]}"
        branch_id: str | None = None
        with self._connection:
            if direction_id and any((company, business)):
                branch_role = role or self._direction_label(owner_id, direction_id)
                normalized_key = "|".join(
                    self._normalize_identity(value)
                    for value in (company or "", business or "", branch_role or "")
                )
                existing_branch = self._connection.execute(
                    """SELECT id FROM direction_branches
                    WHERE owner_id = ? AND direction_id = ? AND normalized_key = ?""",
                    (owner_id, direction_id, normalized_key),
                ).fetchone()
                if existing_branch is None:
                    branch_id = f"branch-{uuid.uuid4().hex[:12]}"
                    self._connection.execute(
                        """INSERT INTO direction_branches
                        (owner_id,id,direction_id,company,business,role,location,
                         normalized_key,status,source_batch_id,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            owner_id, branch_id, direction_id, company or "", business or "",
                            branch_role or "", location or "", normalized_key,
                            "active" if explicitness == "explicit" else "candidate",
                            batch_id, now, now,
                        ),
                    )
                else:
                    branch_id = str(existing_branch["id"])
                    if explicitness == "explicit":
                        self._connection.execute(
                            """UPDATE direction_branches
                            SET status = 'active', source_batch_id = ?, updated_at = ?
                            WHERE owner_id = ? AND id = ? AND status = 'candidate'""",
                            (batch_id, now, owner_id, branch_id),
                        )
            self._connection.execute(
                """INSERT INTO compass_update_batches
                (owner_id,id,run_id,conversation_id,direction_id,branch_id,source_quote,
                 status,created_at) VALUES (?,?,?,?,?,?,?,'committed',?)""",
                (owner_id, batch_id, run_id, conversation_id, direction_id, branch_id,
                 source_quote, now),
            )
            values = [("direction", label)] if label and signal_kind == "direction" else []
            values.extend((kind, value) for kind, value in (
                ("company", company), ("business", business), ("role", role),
                ("location", location),
            ) if value)
            values.extend(("constraint", value) for value in constraints)
            for kind, value in values:
                self._connection.execute(
                    """INSERT INTO compass_update_items
                    (owner_id,id,batch_id,kind,value,explicitness,status,source_quote,created_at)
                    VALUES (?,?,?,?,?,?,?, ?,?)""",
                    (owner_id, f"update-{uuid.uuid4().hex[:12]}", batch_id, kind, value,
                     explicitness, "applied" if explicitness == "explicit" else "pending",
                    source_quote, now),
                )
            if explicitness == "explicit":
                profile_values = [
                    *(('现实约束', value) for value in constraints),
                    *((('地点偏好', location),) if location else ()),
                ]
                for category, value in profile_values:
                    exists = self._connection.execute(
                        """SELECT 1 FROM career_profile_items
                        WHERE owner_id = ? AND category = ? AND value = ?
                          AND status != 'archived'""",
                        (owner_id, category, value),
                    ).fetchone()
                    if exists is None:
                        self._connection.execute(
                            """INSERT INTO career_profile_items
                            (owner_id,id,category,value,explicitness,status,source_batch_id,
                             source_quote,created_at,updated_at)
                            VALUES (?,?,?,?,?,'confirmed',?,?,?,?)""",
                            (
                                owner_id,
                                f"profile-{uuid.uuid4().hex[:12]}",
                                category,
                                value,
                                explicitness,
                                batch_id,
                                source_quote,
                                now,
                                now,
                            ),
                        )
            if direction_id and branch_id and explicitness == "explicit":
                query = " ".join(
                    value for value in (company, business, role or label) if value
                )
                self._ensure_contextual_collection_job(
                    owner_id,
                    direction_id=direction_id,
                    compass_branch_id=branch_id,
                    purpose="job_opportunity",
                    query=query,
                )
                self._ensure_draft_journey_branch(
                    owner_id,
                    direction_id=direction_id,
                    compass_branch_id=branch_id,
                    title="｜".join(
                        value for value in (company, business) if value
                    ) or (role or label or "目标分支"),
                    now=now,
                )
        return self._compass_batch_payload(owner_id, batch_id)

    def list_compass_update_batches(self, owner_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """SELECT id FROM compass_update_batches WHERE owner_id = ?
            ORDER BY created_at DESC""",
            (owner_id,),
        ).fetchall()
        return [self._compass_batch_payload(owner_id, str(row["id"])) for row in rows]

    def undo_compass_update(
        self, owner_id: str, batch_id: str
    ) -> dict[str, object] | None:
        batch = self._connection.execute(
            "SELECT * FROM compass_update_batches WHERE owner_id = ? AND id = ?",
            (owner_id, batch_id),
        ).fetchone()
        if batch is None:
            return None
        if batch["status"] == "undone":
            return {"status": "undone"}
        now = datetime.now(UTC).isoformat()
        with self._connection:
            self._connection.execute(
                """UPDATE compass_update_batches
                SET status = 'undone', undone_at = ? WHERE owner_id = ? AND id = ?""",
                (now, owner_id, batch_id),
            )
            self._connection.execute(
                """UPDATE compass_update_items SET status = 'undone'
                WHERE owner_id = ? AND batch_id = ?""",
                (owner_id, batch_id),
            )
            self._connection.execute(
                """UPDATE career_profile_items SET status = 'archived', updated_at = ?
                WHERE owner_id = ? AND source_batch_id = ?""",
                (now, owner_id, batch_id),
            )
            reaffirmed = None
            if batch["branch_id"]:
                reaffirmed = self._connection.execute(
                    """SELECT 1 FROM compass_update_batches
                    WHERE owner_id = ? AND branch_id = ? AND id != ?
                      AND status = 'committed' LIMIT 1""",
                    (owner_id, batch["branch_id"], batch_id),
                ).fetchone()
            if reaffirmed is None:
                self._connection.execute(
                    """UPDATE direction_branches
                    SET status = 'archived', updated_at = ?
                    WHERE owner_id = ? AND source_batch_id = ?""",
                    (now, owner_id, batch_id),
                )
                self._connection.execute(
                    """UPDATE contextual_collection_jobs SET status = 'cancelled',
                        updated_at = ?
                    WHERE owner_id = ? AND compass_branch_id = ?
                      AND status IN ('queued', 'collecting')""",
                    (now, owner_id, batch["branch_id"]),
                )
            if batch["direction_id"]:
                journey = self._connection.execute(
                    "SELECT 1 FROM journeys WHERE owner_id = ? AND direction_id = ?",
                    (owner_id, batch["direction_id"]),
                ).fetchone()
                later_batch = self._connection.execute(
                    """SELECT 1 FROM compass_update_batches
                    WHERE owner_id = ? AND direction_id = ? AND id != ?
                      AND status = 'committed' LIMIT 1""",
                    (owner_id, batch["direction_id"], batch_id),
                ).fetchone()
                if journey is None and later_batch is None:
                    self._connection.execute(
                        """UPDATE directions SET status = 'archived', updated_at = ?
                        WHERE owner_id = ? AND id = ? AND source_signal_id IN
                          (SELECT id FROM direction_signals
                           WHERE owner_id = ? AND source_run_id = ?)""",
                        (now, owner_id, batch["direction_id"], owner_id, batch["run_id"]),
                    )
        return {"status": "undone"}

    def correct_compass_update_item(
        self, owner_id: str, batch_id: str, item_id: str, value: str
    ) -> dict[str, object] | None:
        normalized_value = " ".join(value.split())
        if not normalized_value:
            raise ValueError("value must not be empty")
        item = self._connection.execute(
            """SELECT i.*, b.direction_id, b.branch_id
            FROM compass_update_items i
            JOIN compass_update_batches b ON b.owner_id = i.owner_id
                AND b.id = i.batch_id
            WHERE i.owner_id = ? AND i.batch_id = ? AND i.id = ?
              AND b.status = 'committed'""",
            (owner_id, batch_id, item_id),
        ).fetchone()
        if item is None:
            return None
        now = datetime.now(UTC).isoformat()
        with self._connection:
            self._connection.execute(
                """UPDATE compass_update_items SET value = ?, status = 'applied'
                WHERE owner_id = ? AND id = ?""",
                (normalized_value, owner_id, item_id),
            )
            if item["kind"] == "direction" and item["direction_id"]:
                self._connection.execute(
                    """UPDATE directions SET label = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?""",
                    (normalized_value, now, owner_id, item["direction_id"]),
                )
            if item["kind"] in {"company", "business", "role", "location"} and item["branch_id"]:
                self._connection.execute(
                    f"UPDATE direction_branches SET {item['kind']} = ?, updated_at = ? "
                    "WHERE owner_id = ? AND id = ?",
                    (normalized_value, now, owner_id, item["branch_id"]),
                )
                branch = self._connection.execute(
                    """SELECT company,business,role FROM direction_branches
                    WHERE owner_id = ? AND id = ?""",
                    (owner_id, item["branch_id"]),
                ).fetchone()
                assert branch is not None
                key = "|".join(
                    self._normalize_identity(str(branch[field]))
                    for field in ("company", "business", "role")
                )
                self._connection.execute(
                    """UPDATE direction_branches SET normalized_key = ?
                    WHERE owner_id = ? AND id = ?""",
                    (key, owner_id, item["branch_id"]),
                )
        return self._compass_batch_payload(owner_id, batch_id)

    def _compass_batch_payload(self, owner_id: str, batch_id: str) -> dict[str, object]:
        batch = self._connection.execute(
            "SELECT * FROM compass_update_batches WHERE owner_id = ? AND id = ?",
            (owner_id, batch_id),
        ).fetchone()
        if batch is None:
            raise LookupError(batch_id)
        result = self._decode(batch)
        result["items"] = [
            self._decode(row) for row in self._connection.execute(
                """SELECT * FROM compass_update_items
                WHERE owner_id = ? AND batch_id = ? ORDER BY rowid""",
                (owner_id, batch_id),
            ).fetchall()
        ]
        return result

    def _direction_label(self, owner_id: str, direction_id: str) -> str:
        row = self._connection.execute(
            "SELECT label FROM directions WHERE owner_id = ? AND id = ?",
            (owner_id, direction_id),
        ).fetchone()
        return str(row["label"]) if row is not None else ""

    @staticmethod
    def _normalize_identity(value: str) -> str:
        return "".join(value.lower().split())

    def _find_matching_direction(
        self, owner_id: str, *candidates: str | None
    ) -> str | None:
        normalized = {
            self._normalize_identity(candidate)
            for candidate in candidates
            if candidate and candidate.strip()
        }
        if not normalized:
            return None
        rows = self._connection.execute(
            """SELECT id, label FROM directions
            WHERE owner_id = ? AND status != 'archived'
            ORDER BY updated_at DESC""",
            (owner_id,),
        ).fetchall()
        for row in rows:
            if self._normalize_identity(str(row["label"])) in normalized:
                return str(row["id"])
        return None

    def list_journey_branches(self, owner_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """SELECT jb.*, COALESCE(db.company, '') AS company,
                      COALESCE(db.business, '') AS business,
                      COALESCE(db.role, '') AS role,
                      COALESCE(db.location, '') AS location
            FROM journey_branches jb
            LEFT JOIN direction_branches db
              ON db.owner_id = jb.owner_id AND db.id = jb.compass_branch_id
            WHERE jb.owner_id = ?
            ORDER BY jb.updated_at DESC""",
            (owner_id,),
        ).fetchall()
        return [self._decode(row) for row in rows]

    def _repair_unbound_explicit_targets(self) -> None:
        rows = self._connection.execute(
            """SELECT s.*, b.id AS batch_id
            FROM direction_signals s
            JOIN compass_update_batches b
              ON b.owner_id = s.owner_id AND b.run_id = s.source_run_id
            WHERE s.signal_kind = 'target' AND s.explicitness = 'explicit'
              AND s.status = 'accepted' AND b.status = 'committed'
              AND b.direction_id IS NULL"""
        ).fetchall()
        for row in rows:
            try:
                context = json.loads(str(row["context_json"]))
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(context, dict):
                continue
            company = context.get("company")
            business = context.get("business")
            role = context.get("role")
            location = context.get("location")
            if not any(isinstance(value, str) and value.strip() for value in (company, business)):
                continue
            direction_id = self._find_matching_direction(
                str(row["owner_id"]),
                role if isinstance(role, str) else None,
                str(row["label"]),
            )
            if direction_id is None:
                continue
            owner_id = str(row["owner_id"])
            company_value = company.strip() if isinstance(company, str) else ""
            business_value = business.strip() if isinstance(business, str) else ""
            role_value = (
                role.strip() if isinstance(role, str) and role.strip()
                else self._direction_label(owner_id, direction_id)
            )
            location_value = location.strip() if isinstance(location, str) else ""
            normalized_key = "|".join(
                self._normalize_identity(value)
                for value in (company_value, business_value, role_value)
            )
            existing = self._connection.execute(
                """SELECT id FROM direction_branches
                WHERE owner_id = ? AND direction_id = ? AND normalized_key = ?""",
                (owner_id, direction_id, normalized_key),
            ).fetchone()
            now = str(row["updated_at"])
            if existing is None:
                branch_id = f"branch-{uuid.uuid4().hex[:12]}"
                self._connection.execute(
                    """INSERT INTO direction_branches
                    (owner_id,id,direction_id,company,business,role,location,
                     normalized_key,status,source_batch_id,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        owner_id, branch_id, direction_id, company_value, business_value,
                        role_value, location_value, normalized_key, "active",
                        row["batch_id"], now, now,
                    ),
                )
            else:
                branch_id = str(existing["id"])
            self._connection.execute(
                """UPDATE compass_update_batches
                SET direction_id = ?, branch_id = ?
                WHERE owner_id = ? AND id = ? AND direction_id IS NULL""",
                (direction_id, branch_id, owner_id, row["batch_id"]),
            )
            self._ensure_draft_journey_branch(
                owner_id,
                direction_id=direction_id,
                compass_branch_id=branch_id,
                title="｜".join(
                    value for value in (company_value, business_value) if value
                ) or role_value,
                now=now,
            )
            self._ensure_contextual_collection_job(
                owner_id,
                direction_id=direction_id,
                compass_branch_id=branch_id,
                purpose="job_opportunity",
                query=" ".join(
                    value for value in (company_value, business_value, role_value) if value
                ),
            )

    def _ensure_draft_journey_branch(
        self,
        owner_id: str,
        *,
        direction_id: str,
        compass_branch_id: str,
        title: str,
        now: str,
    ) -> None:
        journey = self._connection.execute(
            "SELECT id FROM journeys WHERE owner_id = ? AND direction_id = ?",
            (owner_id, direction_id),
        ).fetchone()
        if journey is None:
            return
        self._connection.execute(
            """INSERT OR IGNORE INTO journey_branches
            (owner_id,id,journey_id,compass_branch_id,kind,title,status,priority,
             rationale,created_at,updated_at)
            VALUES (?,?,?,?, 'target',?,'draft',0,?,?,?)""",
            (
                owner_id,
                f"jbranch-{uuid.uuid4().hex[:12]}",
                journey["id"],
                compass_branch_id,
                title,
                "这个目标已在罗盘中，确认开始准备后才生成差异行动。",
                now,
                now,
            ),
        )

    def accept_direction_signal(
        self, owner_id: str, signal_id: str
    ) -> dict[str, object] | None:
        signal = self._connection.execute(
            "SELECT * FROM direction_signals WHERE owner_id = ? AND id = ?",
            (owner_id, signal_id),
        ).fetchone()
        if signal is None or signal["signal_kind"] != "direction":
            return None
        now = datetime.now(UTC).isoformat()
        with self._connection:
            if signal["status"] != "accepted":
                self._connection.execute(
                    """UPDATE direction_signals SET status = 'accepted', updated_at = ?
                    WHERE owner_id = ? AND id = ?""",
                    (now, owner_id, signal_id),
                )
            direction_id = self._create_direction_from_signal(owner_id, signal_id, now)
        if direction_id is None:
            return None
        row = self._connection.execute(
            "SELECT * FROM directions WHERE owner_id = ? AND id = ?",
            (owner_id, direction_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def list_directions(self, owner_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """SELECT * FROM directions
            WHERE owner_id = ? AND status != 'archived'
            ORDER BY updated_at DESC""",
            (owner_id,),
        ).fetchall()
        return [self._decode(row) for row in rows]

    def _create_direction_from_signal(
        self, owner_id: str, signal_id: str, now: str
    ) -> str | None:
        existing = self._connection.execute(
            "SELECT id FROM directions WHERE owner_id = ? AND source_signal_id = ?",
            (owner_id, signal_id),
        ).fetchone()
        if existing is not None:
            direction_id = str(existing["id"])
            direction = self._connection.execute(
                "SELECT label FROM directions WHERE owner_id = ? AND id = ?",
                (owner_id, direction_id),
            ).fetchone()
            if direction is not None:
                self._ensure_collection_job(
                    owner_id, direction_id, "job_opportunity", str(direction["label"])
                )
            return direction_id
        signal = self._connection.execute(
            "SELECT * FROM direction_signals WHERE owner_id = ? AND id = ?",
            (owner_id, signal_id),
        ).fetchone()
        if signal is None:
            return None
        matching = self._connection.execute(
            """SELECT id FROM directions
            WHERE owner_id = ? AND status != 'archived'
              AND lower(trim(label)) = lower(trim(?))
            ORDER BY updated_at DESC LIMIT 1""",
            (owner_id, signal["label"]),
        ).fetchone()
        if matching is not None:
            direction_id = str(matching["id"])
            self._ensure_collection_job(
                owner_id, direction_id, "job_opportunity", str(signal["label"])
            )
            return direction_id
        direction_id = f"direction-{uuid.uuid4().hex[:12]}"
        self._connection.execute(
            """INSERT INTO directions
            (owner_id,id,label,status,source_signal_id,source_kind,source_quote,
             reason,confidence,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                owner_id,
                direction_id,
                signal["label"],
                "confirmed",
                signal_id,
                "conversation",
                signal["source_quote"],
                signal["reason"],
                signal["confidence"],
                now,
                now,
            ),
        )
        self._ensure_collection_job(
            owner_id, direction_id, "job_opportunity", str(signal["label"])
        )
        return direction_id

    def list_collection_jobs(
        self, owner_id: str, direction_id: str | None = None
    ) -> list[dict[str, object]]:
        where = "owner_id = ?"
        params: list[object] = [owner_id]
        if direction_id is not None:
            where += " AND direction_id = ?"
            params.append(direction_id)
        rows = self._connection.execute(
            f"""SELECT * FROM knowledge_collection_jobs WHERE {where}
            ORDER BY CASE purpose
                WHEN 'job_opportunity' THEN 1
                WHEN 'interview_archive' THEN 2
                WHEN 'learning_resource' THEN 3
                ELSE 4 END, created_at""",
            params,
        ).fetchall()
        contextual_where = "owner_id = ?"
        contextual_params: list[object] = [owner_id]
        if direction_id is not None:
            contextual_where += " AND direction_id = ?"
            contextual_params.append(direction_id)
        contextual = self._connection.execute(
            f"""SELECT * FROM contextual_collection_jobs
            WHERE {contextual_where} ORDER BY created_at""",
            contextual_params,
        ).fetchall()
        result = [self._decode(row) for row in (*rows, *contextual)]
        order = {"job_opportunity": 1, "interview_archive": 2, "learning_resource": 3}
        return sorted(
            result,
            key=lambda item: (
                order.get(str(item["purpose"]), 4),
                str(item["created_at"]),
            ),
        )

    def claim_collection_jobs(
        self,
        owner_id: str,
        *,
        purpose: str | None = None,
        limit: int = 3,
    ) -> list[dict[str, object]]:
        where = "owner_id = ? AND status = 'queued'"
        params: list[object] = [owner_id]
        if purpose is not None:
            where += " AND purpose = ?"
            params.append(purpose)
        with self._connection:
            rows = self._connection.execute(
                f"""SELECT * FROM knowledge_collection_jobs WHERE {where}
                ORDER BY created_at LIMIT ?""",
                (*params, limit),
            ).fetchall()
            now = datetime.now(UTC).isoformat()
            claimed: list[dict[str, object]] = []
            for row in rows:
                changed = self._connection.execute(
                    """UPDATE knowledge_collection_jobs
                    SET status = 'collecting', attempts = attempts + 1,
                        updated_at = ?, last_error = NULL
                    WHERE owner_id = ? AND id = ? AND status = 'queued'""",
                    (now, owner_id, row["id"]),
                )
                if changed.rowcount:
                    current = self._connection.execute(
                        """SELECT * FROM knowledge_collection_jobs
                        WHERE owner_id = ? AND id = ?""",
                        (owner_id, row["id"]),
                    ).fetchone()
                    assert current is not None
                    claimed.append(self._decode(current))
            remaining = max(0, limit - len(claimed))
            if remaining:
                context_where = "owner_id = ? AND status = 'queued'"
                context_params: list[object] = [owner_id]
                if purpose is not None:
                    context_where += " AND purpose = ?"
                    context_params.append(purpose)
                context_rows = self._connection.execute(
                    f"""SELECT * FROM contextual_collection_jobs
                    WHERE {context_where} ORDER BY created_at LIMIT ?""",
                    (*context_params, remaining),
                ).fetchall()
                for row in context_rows:
                    changed = self._connection.execute(
                        """UPDATE contextual_collection_jobs
                        SET status = 'collecting', attempts = attempts + 1,
                            updated_at = ?, last_error = NULL
                        WHERE owner_id = ? AND id = ? AND status = 'queued'""",
                        (now, owner_id, row["id"]),
                    )
                    if changed.rowcount:
                        current = self._connection.execute(
                            """SELECT * FROM contextual_collection_jobs
                            WHERE owner_id = ? AND id = ?""",
                            (owner_id, row["id"]),
                        ).fetchone()
                        assert current is not None
                        claimed.append(self._decode(current))
        return claimed

    def finish_collection_job(
        self,
        owner_id: str,
        job_id: str,
        *,
        status: str,
        result_count: int = 0,
        last_error: str | None = None,
    ) -> None:
        if status not in {"completed", "partial", "failed"}:
            raise ValueError("invalid terminal collection status")
        with self._connection:
            changed = self._connection.execute(
                """UPDATE knowledge_collection_jobs
                SET status = ?, result_count = ?, last_error = ?, updated_at = ?
                WHERE owner_id = ? AND id = ?""",
                (
                    status,
                    max(0, result_count),
                    last_error[:200] if last_error else None,
                    datetime.now(UTC).isoformat(),
                    owner_id,
                    job_id,
                ),
            )
            if not changed.rowcount:
                self._connection.execute(
                    """UPDATE contextual_collection_jobs
                    SET status = ?, result_count = ?, last_error = ?,
                        last_verified_at = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?""",
                    (
                        status,
                        max(0, result_count),
                        last_error[:200] if last_error else None,
                        (
                            datetime.now(UTC).isoformat()
                            if status in {"completed", "partial"}
                            else None
                        ),
                        datetime.now(UTC).isoformat(),
                        owner_id,
                        job_id,
                    ),
                )

    def queue_collection_refresh(self, owner_id: str, *, purpose: str) -> None:
        with self._connection:
            self._connection.execute(
                """UPDATE knowledge_collection_jobs
                SET status = 'queued', updated_at = ?
                WHERE owner_id = ? AND purpose = ?
                  AND status IN ('completed', 'partial', 'failed')""",
                (datetime.now(UTC).isoformat(), owner_id, purpose),
            )
            self._connection.execute(
                """UPDATE contextual_collection_jobs
                SET status = 'queued', updated_at = ?
                WHERE owner_id = ? AND purpose = ?
                  AND status IN ('completed', 'partial', 'failed')""",
                (datetime.now(UTC).isoformat(), owner_id, purpose),
            )

    def _ensure_collection_job(
        self,
        owner_id: str,
        direction_id: str,
        purpose: str,
        query: str,
        *,
        journey_id: str | None = None,
    ) -> sqlite3.Row:
        existing = self._connection.execute(
            """SELECT * FROM knowledge_collection_jobs
            WHERE owner_id = ? AND direction_id = ? AND purpose = ?""",
            (owner_id, direction_id, purpose),
        ).fetchone()
        if existing is not None:
            return existing
        now = datetime.now(UTC).isoformat()
        job_id = f"collect-{uuid.uuid4().hex[:12]}"
        self._connection.execute(
            """INSERT INTO knowledge_collection_jobs
            (owner_id,id,direction_id,journey_id,purpose,query,status,attempts,
             created_at,updated_at)
            VALUES (?,?,?,?,?,?,'queued',0,?,?)""",
            (owner_id, job_id, direction_id, journey_id, purpose, query, now, now),
        )
        row = self._connection.execute(
            """SELECT * FROM knowledge_collection_jobs
            WHERE owner_id = ? AND id = ?""",
            (owner_id, job_id),
        ).fetchone()
        assert row is not None
        return row

    def _ensure_contextual_collection_job(
        self,
        owner_id: str,
        *,
        direction_id: str,
        compass_branch_id: str,
        purpose: str,
        query: str,
        journey_id: str | None = None,
        journey_branch_id: str | None = None,
    ) -> sqlite3.Row:
        normalized_query_key = "|".join((
            direction_id,
            compass_branch_id,
            journey_branch_id or "",
            purpose,
            self._normalize_identity(query),
        ))
        existing = self._connection.execute(
            """SELECT * FROM contextual_collection_jobs
            WHERE owner_id = ? AND normalized_query_key = ?""",
            (owner_id, normalized_query_key),
        ).fetchone()
        if existing is not None:
            return existing
        now = datetime.now(UTC).isoformat()
        job_id = f"collect-{uuid.uuid4().hex[:12]}"
        self._connection.execute(
            """INSERT INTO contextual_collection_jobs
            (owner_id,id,direction_id,compass_branch_id,journey_id,journey_branch_id,
             purpose,query,normalized_query_key,status,attempts,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,'queued',0,?,?)""",
            (
                owner_id, job_id, direction_id, compass_branch_id, journey_id,
                journey_branch_id, purpose, query, normalized_query_key, now, now,
            ),
        )
        row = self._connection.execute(
            """SELECT * FROM contextual_collection_jobs
            WHERE owner_id = ? AND id = ?""",
            (owner_id, job_id),
        ).fetchone()
        assert row is not None
        return row

    def start_direction_journey(
        self, owner_id: str, direction_id: str
    ) -> dict[str, object] | None:
        direction = self._connection.execute(
            """SELECT * FROM directions
            WHERE owner_id = ? AND id = ? AND status = 'confirmed'""",
            (owner_id, direction_id),
        ).fetchone()
        if direction is None:
            return None
        with self._connection:
            journey = self._connection.execute(
                "SELECT * FROM journeys WHERE owner_id = ? AND direction_id = ?",
                (owner_id, direction_id),
            ).fetchone()
            if journey is None:
                now = datetime.now(UTC).isoformat()
                journey_id = f"journey-{uuid.uuid4().hex[:12]}"
                self._connection.execute(
                    """INSERT INTO journeys
                    (owner_id,id,direction_id,title,status,why,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        owner_id,
                        journey_id,
                        direction_id,
                        direction["label"],
                        "active",
                        "从你确认的罗盘方向开始，逐步补齐真实岗位、面试证据和学习资源。",
                        now,
                        now,
                    ),
                )
            else:
                journey_id = str(journey["id"])
            now = datetime.now(UTC).isoformat()
            common = self._connection.execute(
                """SELECT * FROM journey_branches
                WHERE owner_id = ? AND journey_id = ? AND kind = 'common'""",
                (owner_id, journey_id),
            ).fetchone()
            if common is None:
                common_branch_id = f"jbranch-{uuid.uuid4().hex[:12]}"
                self._connection.execute(
                    """INSERT INTO journey_branches
                    (owner_id,id,journey_id,compass_branch_id,kind,title,status,priority,
                     rationale,created_at,updated_at)
                    VALUES (?,?,?,NULL,'common',?,'active',0,?,?,?)""",
                    (
                        owner_id, common_branch_id, journey_id,
                        f"{direction['label']} · 通用主线",
                        "所有目标分支共享且只保留一份的基础行动。", now, now,
                    ),
                )
            else:
                common_branch_id = str(common["id"])
            compass_branches = self._connection.execute(
                """SELECT * FROM direction_branches
                WHERE owner_id = ? AND direction_id = ? AND status != 'archived'""",
                (owner_id, direction_id),
            ).fetchall()
            for compass_branch in compass_branches:
                title = "｜".join(
                    value for value in (
                        str(compass_branch["company"]), str(compass_branch["business"])
                    ) if value
                ) or str(compass_branch["role"])
                self._connection.execute(
                    """INSERT OR IGNORE INTO journey_branches
                    (owner_id,id,journey_id,compass_branch_id,kind,title,status,priority,
                     rationale,created_at,updated_at)
                    VALUES (?,?,?,?, 'target',?,'draft',0,?,?,?)""",
                    (
                        owner_id, f"jbranch-{uuid.uuid4().hex[:12]}", journey_id,
                        compass_branch["id"], title,
                        "这个目标已在罗盘中，确认开始准备后才生成差异行动。", now, now,
                    ),
                )
            jobs = {
                purpose: self._ensure_collection_job(
                    owner_id,
                    direction_id,
                    purpose,
                    str(direction["label"]),
                    journey_id=journey_id if purpose != "job_opportunity" else None,
                )
                for purpose in (
                    "job_opportunity",
                    "interview_archive",
                    "learning_resource",
                )
            }
            steps = (
                ("role_profile", "查看当前岗位画像与可信招聘信息", "第 1 步", "job_opportunity"),
                ("interview_archive", "查看往年题目与面经证据", "第 2 步", "interview_archive"),
                ("learning_resource", "选择学习资源补齐准备重点", "第 3 步", "learning_resource"),
            )
            for step_kind, title, due, purpose in steps:
                self._connection.execute(
                    """INSERT OR IGNORE INTO journey_tasks
                    (owner_id,id,title,due,state,related,hypothesis_id,why,reflection,
                     journey_id,direction_id,step_kind,collection_job_id,created_via,
                     journey_branch_id,scope)
                    VALUES (?,?,?,?,?,?,NULL,?,NULL,?,?,?,?,'journey',?,'common')""",
                    (
                        owner_id,
                        f"task-{uuid.uuid4().hex[:10]}",
                        title,
                        due,
                        "准备开始",
                        direction["label"],
                        "只使用有来源的真实材料推进这一步。",
                        journey_id,
                        direction_id,
                        step_kind,
                        jobs[purpose]["id"],
                        common_branch_id,
                    ),
                )
        return self._direction_journey_payload(owner_id, journey_id)

    def activate_journey_branch(
        self, owner_id: str, journey_id: str, branch_id: str
    ) -> dict[str, object] | None:
        branch = self._connection.execute(
            """SELECT jb.*, db.company, db.business, db.role, db.direction_id
            FROM journey_branches jb
            JOIN direction_branches db ON db.owner_id = jb.owner_id
                AND db.id = jb.compass_branch_id
            WHERE jb.owner_id = ? AND jb.id = ? AND jb.journey_id = ?
              AND jb.kind = 'target'""",
            (owner_id, branch_id, journey_id),
        ).fetchone()
        if branch is None:
            return None
        now = datetime.now(UTC).isoformat()
        title = str(branch["title"])
        suffix = branch_id.removeprefix("jbranch-")[:8]
        with self._connection:
            if branch["status"] != "active":
                self._connection.execute(
                    """UPDATE journey_branches SET status = 'active', updated_at = ?
                    WHERE owner_id = ? AND id = ?""",
                    (now, owner_id, branch_id),
                )
            steps = (
                (f"target_research_{suffix}", f"拆解 {title} 的真实岗位与业务差异", "分支第 1 步"),
                (f"target_prepare_{suffix}", f"准备 {title} 的差异化案例与面试证据", "分支第 2 步"),
            )
            for step_kind, task_title, due in steps:
                self._connection.execute(
                    """INSERT OR IGNORE INTO journey_tasks
                    (owner_id,id,title,due,state,related,hypothesis_id,why,reflection,
                     journey_id,direction_id,step_kind,created_via,journey_branch_id,scope)
                    VALUES (?,?,?,?,?,?,NULL,?,NULL,?,?,?,'journey',?,'branch_specific')""",
                    (
                        owner_id, f"task-{uuid.uuid4().hex[:10]}", task_title, due,
                        "准备开始", title, "只增加这个目标与通用主线不同的准备。",
                        journey_id, branch["direction_id"], step_kind, branch_id,
                    ),
                )
            query = " ".join(
                value for value in (
                    str(branch["company"]), str(branch["business"]), str(branch["role"])
                ) if value
            )
            for purpose in ("interview_archive", "learning_resource"):
                self._ensure_contextual_collection_job(
                    owner_id,
                    direction_id=str(branch["direction_id"]),
                    compass_branch_id=str(branch["compass_branch_id"]),
                    purpose=purpose,
                    query=query,
                    journey_id=journey_id,
                    journey_branch_id=branch_id,
                )
        return self._direction_journey_payload(owner_id, journey_id)

    def _direction_journey_payload(
        self, owner_id: str, journey_id: str
    ) -> dict[str, object]:
        journey = self._connection.execute(
            "SELECT * FROM journeys WHERE owner_id = ? AND id = ?",
            (owner_id, journey_id),
        ).fetchone()
        assert journey is not None
        tasks = self._connection.execute(
            """SELECT * FROM journey_tasks
            WHERE owner_id = ? AND journey_id = ?
            ORDER BY CASE step_kind
                WHEN 'role_profile' THEN 1
                WHEN 'interview_archive' THEN 2
                WHEN 'learning_resource' THEN 3
                ELSE 4 END""",
            (owner_id, journey_id),
        ).fetchall()
        return {
            "journey": self._decode(journey),
            "tasks": [self._decode(task) for task in tasks],
            "branches": [
                self._decode(branch) for branch in self._connection.execute(
                    """SELECT * FROM journey_branches
                    WHERE owner_id = ? AND journey_id = ?
                    ORDER BY CASE kind WHEN 'common' THEN 0 ELSE 1 END, created_at""",
                    (owner_id, journey_id),
                ).fetchall()
            ],
            "collection_jobs": self.list_collection_jobs(
                owner_id, str(journey["direction_id"])
            ),
        }

    def get_direction_journey(
        self, owner_id: str, journey_id: str
    ) -> dict[str, object] | None:
        exists = self._connection.execute(
            "SELECT 1 FROM journeys WHERE owner_id = ? AND id = ?",
            (owner_id, journey_id),
        ).fetchone()
        if exists is None:
            return None
        return self._direction_journey_payload(owner_id, journey_id)

    def save_future_letter(
        self,
        owner_id: str,
        *,
        journey_id: str,
        message: str,
        paths: list[dict[str, object]],
    ) -> dict[str, object]:
        if self.get_direction_journey(owner_id, journey_id) is None:
            raise LookupError(journey_id)
        letter_id = f"future-{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(UTC).isoformat()
        with self._connection:
            self._connection.execute(
                """INSERT INTO journey_future_letters
                (owner_id,id,journey_id,message,paths_json,created_at)
                VALUES (?,?,?,?,?,?)""",
                (
                    owner_id,
                    letter_id,
                    journey_id,
                    message,
                    json.dumps(paths, ensure_ascii=False),
                    created_at,
                ),
            )
        return self.get_future_letter(owner_id, journey_id)  # type: ignore[return-value]

    def get_future_letter(
        self, owner_id: str, journey_id: str
    ) -> dict[str, object] | None:
        row = self._connection.execute(
            """SELECT * FROM journey_future_letters
            WHERE owner_id = ? AND journey_id = ? ORDER BY created_at DESC LIMIT 1""",
            (owner_id, journey_id),
        ).fetchone()
        if row is None:
            return None
        takeaway = self._connection.execute(
            """SELECT path_kind,question,created_at FROM journey_future_takeaways
            WHERE owner_id = ? AND letter_id = ?""",
            (owner_id, row["id"]),
        ).fetchone()
        return {
            "id": row["id"],
            "journey_id": row["journey_id"],
            "message": row["message"],
            "paths": json.loads(row["paths_json"]),
            "created_at": row["created_at"],
            "takeaway": dict(takeaway) if takeaway is not None else None,
        }

    def confirm_future_takeaway(
        self,
        owner_id: str,
        *,
        journey_id: str,
        letter_id: str,
        path_kind: str,
        question: str,
    ) -> dict[str, object] | None:
        letter = self._connection.execute(
            """SELECT paths_json FROM journey_future_letters
            WHERE owner_id = ? AND id = ? AND journey_id = ?""",
            (owner_id, letter_id, journey_id),
        ).fetchone()
        if letter is None:
            return None
        paths = json.loads(letter["paths_json"])
        if path_kind not in {path["kind"] for path in paths}:
            return None
        created_at = datetime.now(UTC).isoformat()
        with self._connection:
            self._connection.execute(
                """INSERT INTO journey_future_takeaways
                (owner_id,letter_id,journey_id,path_kind,question,created_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(owner_id,letter_id) DO UPDATE SET
                    path_kind=excluded.path_kind, question=excluded.question,
                    created_at=excluded.created_at""",
                (owner_id, letter_id, journey_id, path_kind, question, created_at),
            )
        return {"path_kind": path_kind, "question": question, "created_at": created_at}

    def record_conversation_turn(
        self,
        owner_id: str,
        conversation_id: str,
        user_message: str,
        agent_message: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        title = user_message.strip()[:80]
        with self._connection:
            self._connection.execute(
                """INSERT INTO conversations
                (owner_id, id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(owner_id, id) DO UPDATE SET
                    updated_at = excluded.updated_at""",
                (owner_id, conversation_id, title, now, now),
            )
            self._connection.executemany(
                """INSERT INTO conversation_messages
                (owner_id, conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    (owner_id, conversation_id, "user", user_message, now),
                    (owner_id, conversation_id, "agent", agent_message, now),
                ),
            )

    def list_conversations(self, owner_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """SELECT c.id, c.title, c.updated_at, COUNT(m.sequence) AS message_count
            FROM conversations AS c
            LEFT JOIN conversation_messages AS m
              ON m.owner_id = c.owner_id AND m.conversation_id = c.id
            WHERE c.owner_id = ?
            GROUP BY c.owner_id, c.id, c.title, c.updated_at
            ORDER BY c.updated_at DESC, c.id""",
            (owner_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(
        self, owner_id: str, conversation_id: str
    ) -> dict[str, object] | None:
        conversation = self._connection.execute(
            """SELECT id, title, updated_at FROM conversations
            WHERE owner_id = ? AND id = ?""",
            (owner_id, conversation_id),
        ).fetchone()
        if conversation is None:
            return None
        messages = self._connection.execute(
            """SELECT role, content FROM conversation_messages
            WHERE owner_id = ? AND conversation_id = ? ORDER BY sequence""",
            (owner_id, conversation_id),
        ).fetchall()
        return {
            **dict(conversation),
            "messages": [dict(message) for message in messages],
        }

    def decide_hypothesis(self, owner_id: str, hypothesis_id: str, decision: str) -> bool:
        status = {"confirm": "已确认", "uncertain": "继续观察"}[decision]
        cursor = self._connection.execute(
            "UPDATE hypotheses SET status = ? WHERE owner_id = ? AND id = ?",
            (status, owner_id, hypothesis_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def create_verification_task(
        self, owner_id: str, hypothesis_id: str
    ) -> dict[str, object] | None:
        hypothesis = self._connection.execute(
            "SELECT * FROM hypotheses WHERE owner_id = ? AND id = ?",
            (owner_id, hypothesis_id),
        ).fetchone()
        if hypothesis is None:
            return None
        existing = self._connection.execute(
            """SELECT * FROM journey_tasks
            WHERE owner_id = ? AND hypothesis_id = ? AND state != '已完成'""",
            (owner_id, hypothesis_id),
        ).fetchone()
        if existing is None:
            task_id = f"task-{uuid.uuid4().hex[:10]}"
            self._connection.execute(
                """INSERT INTO journey_tasks
                (owner_id,id,title,due,state,related,hypothesis_id,why,reflection)
                VALUES (?,?,?,?,?,?,?,?,NULL)""",
                (
                    owner_id,
                    task_id,
                    "用一次真实经历验证这条职业猜想",
                    "本周",
                    "准备开始",
                    hypothesis["statement"],
                    hypothesis_id,
                    "通过现实行动补充证据，而不是只靠想象判断职业方向。",
                ),
            )
            self._connection.commit()
            existing = self._connection.execute(
                "SELECT * FROM journey_tasks WHERE owner_id = ? AND id = ?",
                (owner_id, task_id),
            ).fetchone()
        return self._decode(existing)

    def update_task(self, owner_id: str, task_id: str, state: str, reflection: str | None) -> bool:
        task = self._connection.execute(
            "SELECT * FROM journey_tasks WHERE owner_id = ? AND id = ?",
            (owner_id, task_id),
        ).fetchone()
        if task is None:
            return False
        with self._connection:
            self._connection.execute(
                """UPDATE journey_tasks
                SET state = ?, reflection = COALESCE(?, reflection)
                WHERE owner_id = ? AND id = ?""",
                (state, reflection, owner_id, task_id),
            )
            if state == "已完成" and task["direction_id"]:
                branch_id = None
                if task["journey_branch_id"]:
                    branch = self._connection.execute(
                        """SELECT compass_branch_id FROM journey_branches
                        WHERE owner_id = ? AND id = ?""",
                        (owner_id, task["journey_branch_id"]),
                    ).fetchone()
                    if branch is not None:
                        branch_id = branch["compass_branch_id"]
                content = str(task["title"])
                if reflection:
                    content = f"{content}：{reflection.strip()}"
                self._connection.execute(
                    """INSERT OR IGNORE INTO direction_evidence
                    (owner_id,id,direction_id,branch_id,kind,content,status,source_kind,
                     source_reference,source_quote,created_at)
                    VALUES (?,?,?,?,? ,?,'confirmed','journey_task',?,NULL,?)""",
                    (
                        owner_id,
                        f"evidence-{uuid.uuid4().hex[:12]}",
                        task["direction_id"],
                        branch_id,
                        "fact",
                        content,
                        task_id,
                        datetime.now(UTC).isoformat(),
                    ),
                )
        return True

    def create_journey_event(
        self,
        owner_id: str,
        *,
        title: str,
        start_at: str,
        end_at: str,
        reminder_minutes: int | None = None,
        meeting_url: str | None = None,
        notes: str | None = None,
        created_via: str = "manual",
        related: str = "个人日程",
        why: str = "由你添加到航程日历。",
        source_reference: str | None = None,
    ) -> dict[str, object]:
        if source_reference is not None:
            existing = self._connection.execute(
                """SELECT * FROM journey_tasks
                WHERE owner_id = ? AND source_reference = ?""",
                (owner_id, source_reference),
            ).fetchone()
            if existing is not None:
                return self._decode(existing)
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        due = datetime.fromisoformat(start_at).date().isoformat()
        self._connection.execute(
            """INSERT INTO journey_tasks
            (owner_id,id,title,due,state,related,hypothesis_id,why,reflection,idea_id,
             start_at,end_at,reminder_minutes,meeting_url,notes,created_via,source_reference)
            VALUES (?,?,?,?,?,?,NULL,?,NULL,NULL,?,?,?,?,?,?,?)""",
            (
                owner_id,
                task_id,
                title,
                due,
                "准备开始",
                related,
                why,
                start_at,
                end_at,
                reminder_minutes,
                meeting_url,
                notes,
                created_via,
                source_reference,
            ),
        )
        self._connection.commit()
        row = self._connection.execute(
            "SELECT * FROM journey_tasks WHERE owner_id = ? AND id = ?",
            (owner_id, task_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def _rows(self, table: str, owner_id: str, order: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            f"SELECT * FROM {table} WHERE owner_id = ? ORDER BY {order}", (owner_id,)
        ).fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, object]:
        result = {key: row[key] for key in row.keys() if key != "owner_id"}
        for key in tuple(result):
            if key.endswith("_json"):
                result[key.removesuffix("_json")] = json.loads(str(result.pop(key)))
        return result
