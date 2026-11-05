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
            CREATE TABLE IF NOT EXISTS knowledge_collection_jobs (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, direction_id TEXT NOT NULL,
                journey_id TEXT, purpose TEXT NOT NULL, query TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                result_count INTEGER NOT NULL DEFAULT 0, last_error TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id), UNIQUE(owner_id, direction_id, purpose)
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
            CREATE INDEX IF NOT EXISTS collection_jobs_owner_status_idx
                ON knowledge_collection_jobs(owner_id, status, updated_at DESC);
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
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def dashboard(self, owner_id: str) -> dict[str, object]:
        return {
            "hypotheses": self._rows("hypotheses", owner_id, "id"),
            "journey": self._rows("journey_tasks", owner_id, "rowid"),
            "memories": self._rows("memories", owner_id, "rowid"),
            "dreaming": self._rows("dreaming_insights", owner_id, "rowid DESC"),
            "directions": self.list_directions(owner_id),
            "journeys": self._rows("journeys", owner_id, "updated_at DESC"),
            "collection_jobs": self.list_collection_jobs(owner_id),
            "direction_signals": self._rows(
                "direction_signals", owner_id, "updated_at DESC"
            ),
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
                 confidence,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
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
                    now,
                    now,
                ),
            )
            if explicitness == "explicit":
                self._create_direction_from_signal(owner_id, signal_id, now)
        row = self._connection.execute(
            "SELECT * FROM direction_signals WHERE owner_id = ? AND id = ?",
            (owner_id, signal_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def accept_direction_signal(
        self, owner_id: str, signal_id: str
    ) -> dict[str, object] | None:
        signal = self._connection.execute(
            "SELECT * FROM direction_signals WHERE owner_id = ? AND id = ?",
            (owner_id, signal_id),
        ).fetchone()
        if signal is None:
            return None
        now = datetime.now(UTC).isoformat()
        with self._connection:
            if signal["status"] != "accepted":
                self._connection.execute(
                    """UPDATE direction_signals SET status = 'accepted', updated_at = ?
                    WHERE owner_id = ? AND id = ?""",
                    (now, owner_id, signal_id),
                )
            self._create_direction_from_signal(owner_id, signal_id, now)
        row = self._connection.execute(
            "SELECT * FROM directions WHERE owner_id = ? AND source_signal_id = ?",
            (owner_id, signal_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def list_directions(self, owner_id: str) -> list[dict[str, object]]:
        return self._rows("directions", owner_id, "updated_at DESC")

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
        return [self._decode(row) for row in rows]

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
            self._connection.execute(
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

    def queue_collection_refresh(self, owner_id: str, *, purpose: str) -> None:
        with self._connection:
            self._connection.execute(
                """UPDATE knowledge_collection_jobs
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
                     journey_id,direction_id,step_kind,collection_job_id,created_via)
                    VALUES (?,?,?,?,?,?,NULL,?,NULL,?,?,?,?,'journey')""",
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
                    ),
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
        cursor = self._connection.execute(
            """UPDATE journey_tasks
            SET state = ?, reflection = COALESCE(?, reflection)
            WHERE owner_id = ? AND id = ?""",
            (state, reflection, owner_id, task_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

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
