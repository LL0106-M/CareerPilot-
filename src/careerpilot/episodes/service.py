from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime

from careerpilot.episodes.models import MEANINGFUL_EVENT_KINDS, OPEN_LOOP_KINDS


class EpisodeService:
    """Stores meaningful shared events without turning summaries into user facts."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversation_episodes (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, thread_id TEXT,
                event_kind TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
                user_shift TEXT NOT NULL DEFAULT '', outcome TEXT NOT NULL DEFAULT '',
                callback_cue TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
                source_turn_ids_json TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id),
                UNIQUE(owner_id, source_fingerprint)
            );
            CREATE INDEX IF NOT EXISTS episodes_owner_thread_idx
                ON conversation_episodes(owner_id, thread_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS open_loops (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, thread_id TEXT,
                episode_id TEXT, kind TEXT NOT NULL, initiator TEXT NOT NULL,
                user_need TEXT NOT NULL DEFAULT '', agent_need TEXT NOT NULL DEFAULT '',
                trigger_condition TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS open_loop_episode_kind_idx
                ON open_loops(owner_id, episode_id, kind)
                WHERE episode_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS open_loops_owner_status_idx
                ON open_loops(owner_id, status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS agent_commitments (
                owner_id TEXT NOT NULL, id TEXT NOT NULL, thread_id TEXT,
                open_loop_id TEXT, description TEXT NOT NULL,
                executor_kind TEXT NOT NULL, status TEXT NOT NULL,
                result_reference TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_id, id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS commitment_identity_idx
                ON agent_commitments(owner_id, open_loop_id, description);
            CREATE INDEX IF NOT EXISTS commitments_owner_status_idx
                ON agent_commitments(owner_id, status, updated_at DESC);
            """
        )
        self._connection.commit()

    def record_event(
        self,
        owner_id: str,
        *,
        event_kind: str,
        source_turn_ids: tuple[str, ...],
        title: str,
        summary: str,
        thread_id: str | None = None,
        user_shift: str = "",
        outcome: str = "",
        callback_cue: str = "",
        open_loop: dict[str, str] | None = None,
    ) -> dict[str, object] | None:
        if event_kind not in MEANINGFUL_EVENT_KINDS:
            return None
        normalized_turn_ids = tuple(
            dict.fromkeys(item.strip() for item in source_turn_ids if item.strip())
        )
        if not normalized_turn_ids:
            raise ValueError("an episode must reference at least one source turn")
        fingerprint = hashlib.sha256(
            json.dumps(
                {"event_kind": event_kind, "turn_ids": normalized_turn_ids},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        existing = self._connection.execute(
            """SELECT * FROM conversation_episodes
            WHERE owner_id = ? AND source_fingerprint = ?""",
            (owner_id, fingerprint),
        ).fetchone()
        if existing is not None:
            return self._decode(existing)
        now = datetime.now(UTC).isoformat()
        episode_id = f"episode-{uuid.uuid4().hex[:12]}"
        with self._connection:
            self._connection.execute(
                """INSERT INTO conversation_episodes
                (owner_id,id,thread_id,event_kind,title,summary,user_shift,outcome,
                 callback_cue,status,source_turn_ids_json,source_fingerprint,
                 created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,'active',?,?,?,?)""",
                (
                    owner_id,
                    episode_id,
                    thread_id,
                    event_kind,
                    self._clean(title),
                    self._clean(summary),
                    self._optional(user_shift),
                    self._optional(outcome),
                    self._optional(callback_cue),
                    json.dumps(normalized_turn_ids, ensure_ascii=False),
                    fingerprint,
                    now,
                    now,
                ),
            )
        if open_loop is not None:
            self.create_open_loop(
                owner_id,
                episode_id=episode_id,
                thread_id=thread_id,
                kind=open_loop.get("kind", "evidence_gap"),
                initiator=open_loop.get("initiator", "shared"),
                user_need=open_loop.get("user_need", ""),
                agent_need=open_loop.get("agent_need", ""),
                trigger_condition=open_loop.get("trigger_condition", ""),
            )
        row = self._connection.execute(
            "SELECT * FROM conversation_episodes WHERE owner_id = ? AND id = ?",
            (owner_id, episode_id),
        ).fetchone()
        assert row is not None
        return self._decode(row)

    def create_open_loop(
        self,
        owner_id: str,
        *,
        kind: str,
        initiator: str,
        user_need: str,
        agent_need: str,
        trigger_condition: str,
        episode_id: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, object]:
        if kind not in OPEN_LOOP_KINDS:
            raise ValueError(f"unsupported open loop kind: {kind}")
        if episode_id is not None:
            existing = self._connection.execute(
                """SELECT * FROM open_loops
                WHERE owner_id = ? AND episode_id = ? AND kind = ?""",
                (owner_id, episode_id, kind),
            ).fetchone()
            if existing is not None:
                return self._decode(existing)
        now = datetime.now(UTC).isoformat()
        loop_id = f"loop-{uuid.uuid4().hex[:12]}"
        with self._connection:
            self._connection.execute(
                """INSERT INTO open_loops
                (owner_id,id,thread_id,episode_id,kind,initiator,user_need,agent_need,
                 trigger_condition,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,'active',?,?)""",
                (
                    owner_id,
                    loop_id,
                    thread_id,
                    episode_id,
                    kind,
                    initiator,
                    self._optional(user_need),
                    self._optional(agent_need),
                    self._optional(trigger_condition),
                    now,
                    now,
                ),
            )
        return self._require("open_loops", owner_id, loop_id)

    def create_commitment(
        self,
        owner_id: str,
        *,
        open_loop_id: str,
        description: str,
        executor_kind: str,
    ) -> dict[str, object]:
        loop = self._require("open_loops", owner_id, open_loop_id)
        existing = self._connection.execute(
            """SELECT * FROM agent_commitments
            WHERE owner_id = ? AND open_loop_id = ? AND description = ?""",
            (owner_id, open_loop_id, self._clean(description)),
        ).fetchone()
        if existing is not None:
            return self._decode(existing)
        now = datetime.now(UTC).isoformat()
        commitment_id = f"commitment-{uuid.uuid4().hex[:12]}"
        with self._connection:
            self._connection.execute(
                """INSERT INTO agent_commitments
                (owner_id,id,thread_id,open_loop_id,description,executor_kind,status,
                 result_reference,created_at,updated_at)
                VALUES (?,?,?,?,?,?,'queued',NULL,?,?)""",
                (
                    owner_id,
                    commitment_id,
                    loop["thread_id"],
                    open_loop_id,
                    self._clean(description),
                    self._clean(executor_kind),
                    now,
                    now,
                ),
            )
        return self._require("agent_commitments", owner_id, commitment_id)

    def list_episodes(self, owner_id: str) -> list[dict[str, object]]:
        return self._list("conversation_episodes", owner_id)

    def list_open_loops(self, owner_id: str) -> list[dict[str, object]]:
        return self._list("open_loops", owner_id)

    def list_commitments(self, owner_id: str) -> list[dict[str, object]]:
        return self._list("agent_commitments", owner_id)

    def callback_context(
        self,
        owner_id: str,
        message: str,
        page_context: dict[str, str] | None = None,
    ) -> dict[str, object] | None:
        rows = self._connection.execute(
            """SELECT e.*, t.seed_text
            FROM conversation_episodes e
            LEFT JOIN exploration_threads t
              ON t.owner_id = e.owner_id AND t.id = e.thread_id
            WHERE e.owner_id = ? AND e.status = 'active'
            ORDER BY e.updated_at DESC, e.id""",
            (owner_id,),
        ).fetchall()
        page = (page_context or {}).get("page")
        selected = next(
            (
                row
                for row in rows
                if (row["seed_text"] and str(row["seed_text"]) in message)
                or page == "compass"
            ),
            None,
        )
        if selected is None:
            return None
        episode = self._decode(selected)
        loop = self._connection.execute(
            """SELECT * FROM open_loops
            WHERE owner_id = ? AND episode_id = ? AND status = 'active'
            ORDER BY updated_at DESC LIMIT 1""",
            (owner_id, episode["id"]),
        ).fetchone()
        commitment = None
        if loop is not None:
            commitment = self._connection.execute(
                """SELECT * FROM agent_commitments
                WHERE owner_id = ? AND open_loop_id = ?
                  AND status IN ('queued','running','completed','failed')
                ORDER BY updated_at DESC LIMIT 1""",
                (owner_id, loop["id"]),
            ).fetchone()
        return {
            "episode": episode,
            "open_loop": self._decode(loop) if loop is not None else None,
            "commitment": self._decode(commitment) if commitment is not None else None,
        }

    def _list(self, table: str, owner_id: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            f"SELECT * FROM {table} WHERE owner_id = ? ORDER BY updated_at DESC, id",
            (owner_id,),
        ).fetchall()
        return [self._decode(row) for row in rows]

    def _require(self, table: str, owner_id: str, item_id: str) -> dict[str, object]:
        row = self._connection.execute(
            f"SELECT * FROM {table} WHERE owner_id = ? AND id = ?",
            (owner_id, item_id),
        ).fetchone()
        if row is None:
            raise LookupError(item_id)
        return self._decode(row)

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, object]:
        result = {key: row[key] for key in row.keys() if key != "owner_id"}
        if "source_turn_ids_json" in result:
            result["source_turn_ids"] = json.loads(str(result.pop("source_turn_ids_json")))
        return result

    @staticmethod
    def _clean(value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("episode text must not be empty")
        return cleaned

    @staticmethod
    def _optional(value: str) -> str:
        return " ".join(value.split())
