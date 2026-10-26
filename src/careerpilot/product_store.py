from __future__ import annotations

import json
import sqlite3
import uuid
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
            CREATE INDEX IF NOT EXISTS hypotheses_owner_idx ON hypotheses(owner_id);
            CREATE INDEX IF NOT EXISTS journey_owner_idx ON journey_tasks(owner_id);
            CREATE INDEX IF NOT EXISTS memories_owner_idx ON memories(owner_id);
            CREATE INDEX IF NOT EXISTS dreaming_owner_idx ON dreaming_insights(owner_id);
            """
        )

    def close(self) -> None:
        self._connection.close()

    def dashboard(self, owner_id: str) -> dict[str, object]:
        return {
            "hypotheses": self._rows("hypotheses", owner_id, "id"),
            "journey": self._rows("journey_tasks", owner_id, "rowid"),
            "memories": self._rows("memories", owner_id, "rowid"),
            "dreaming": self._rows("dreaming_insights", owner_id, "rowid DESC"),
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
