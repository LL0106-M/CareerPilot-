from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from careerpilot.agent.orchestration import AgentStage
from careerpilot.harness.events import HarnessEvent


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class AgentRunRecord:
    run_id: str
    owner_id: str
    conversation_id: str
    session_id: str
    objective: str
    status: str
    stage: AgentStage
    runtime_phase: str | None
    step: int
    version: int
    cancellation_requested: bool
    result_json: dict[str, Any]
    error_json: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class RunEventRecord:
    sequence: int
    event_type: str
    stage: str | None
    runtime_phase: str | None
    step: int
    data: dict[str, Any]
    created_at: str


@dataclass(frozen=True, slots=True)
class RunCheckpointRecord:
    run_id: str
    stage: str
    runtime_phase: str | None
    step: int
    state: dict[str, Any]
    version: int
    created_at: str


class SqliteAgentRunStore:
    """Durable run ledger, event log, and latest checkpoint for Agent execution."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                runtime_phase TEXT,
                step INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1,
                cancellation_requested INTEGER NOT NULL DEFAULT 0,
                result_json TEXT NOT NULL DEFAULT '{}',
                error_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS agent_runs_owner_idx
                ON agent_runs(owner_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS agent_run_events (
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT,
                runtime_phase TEXT,
                step INTEGER NOT NULL DEFAULT 0,
                data_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                PRIMARY KEY(run_id, sequence),
                FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_run_checkpoints (
                run_id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                runtime_phase TEXT,
                step INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
            );
            """
        )
        self._connection.commit()
        self._lock = asyncio.Lock()

    async def create(
        self,
        *,
        run_id: str,
        owner_id: str,
        conversation_id: str,
        session_id: str,
        objective: str,
    ) -> AgentRunRecord:
        async with self._lock:
            now = _now()
            self._connection.execute(
                """INSERT OR IGNORE INTO agent_runs(
                    run_id, owner_id, conversation_id, session_id, objective,
                    status, stage, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?)""",
                (
                    run_id,
                    owner_id,
                    conversation_id,
                    session_id,
                    objective,
                    AgentStage.CREATED.value,
                    now,
                    now,
                ),
            )
            self._connection.commit()
            row = self._get_row(run_id)
        return _run_from_row(row)

    async def transition_stage(
        self,
        run_id: str,
        stage: AgentStage,
        *,
        data: dict[str, Any] | None = None,
    ) -> None:
        status = (
            stage.value
            if stage in {
                AgentStage.COMPLETED,
                AgentStage.FAILED,
                AgentStage.CANCELLED,
                AgentStage.BLOCKED,
            }
            else "running"
        )
        async with self._lock:
            self._connection.execute(
                """UPDATE agent_runs SET stage=?, status=?, version=version+1,
                updated_at=? WHERE run_id=?""",
                (stage.value, status, _now(), run_id),
            )
            self._append_event_locked(
                run_id,
                event_type=f"agent.{stage.value}",
                stage=stage.value,
                runtime_phase=None,
                step=0,
                data=data or {},
            )
            self._save_checkpoint_locked(run_id, stage.value, None, 0, data or {})
            self._connection.commit()

    async def append_harness_event(self, event: HarnessEvent) -> None:
        status = {
            "run.failed": "failed",
            "run.cancelled": "cancelled",
        }.get(event.type.value)
        async with self._lock:
            assignments = "runtime_phase=?, step=?, version=version+1, updated_at=?"
            params: list[object] = [event.phase.value, event.step, _now()]
            if status is not None:
                assignments += ", status=?"
                params.append(status)
            params.append(event.run_id)
            self._connection.execute(
                f"UPDATE agent_runs SET {assignments} WHERE run_id=?", params
            )
            self._append_event_locked(
                event.run_id,
                event_type=event.type.value,
                stage=None,
                runtime_phase=event.phase.value,
                step=event.step,
                data=event.data,
            )
            self._save_checkpoint_locked(
                event.run_id,
                None,
                event.phase.value,
                event.step,
                event.as_dict(),
            )
            self._connection.commit()

    async def complete(self, run_id: str, result: dict[str, Any]) -> None:
        async with self._lock:
            self._connection.execute(
                """UPDATE agent_runs SET status='completed', stage=?, result_json=?,
                version=version+1, updated_at=? WHERE run_id=?""",
                (
                    AgentStage.COMPLETED.value,
                    json.dumps(result, ensure_ascii=False),
                    _now(),
                    run_id,
                ),
            )
            self._append_event_locked(
                run_id,
                event_type="agent.completed",
                stage=AgentStage.COMPLETED.value,
                runtime_phase=None,
                step=0,
                data=result,
            )
            self._connection.commit()

    async def fail(self, run_id: str, exc: Exception) -> None:
        error = {"error_type": type(exc).__name__, "message": str(exc)[:1000]}
        async with self._lock:
            self._connection.execute(
                """UPDATE agent_runs SET status='failed', stage=?, error_json=?,
                version=version+1, updated_at=? WHERE run_id=?""",
                (AgentStage.FAILED.value, json.dumps(error, ensure_ascii=False), _now(), run_id),
            )
            self._append_event_locked(
                run_id,
                event_type="agent.failed",
                stage=AgentStage.FAILED.value,
                runtime_phase=None,
                step=0,
                data=error,
            )
            self._connection.commit()

    async def request_cancel(self, owner_id: str, run_id: str) -> bool:
        async with self._lock:
            cursor = self._connection.execute(
                """UPDATE agent_runs SET cancellation_requested=1, version=version+1,
                updated_at=? WHERE owner_id=? AND run_id=? AND status='running'""",
                (_now(), owner_id, run_id),
            )
            if cursor.rowcount:
                self._append_event_locked(
                    run_id,
                    event_type="run.cancel_requested",
                    stage=None,
                    runtime_phase=None,
                    step=0,
                    data={},
                )
            self._connection.commit()
            return cursor.rowcount > 0

    async def cancellation_requested(self, run_id: str) -> bool:
        async with self._lock:
            row = self._connection.execute(
                "SELECT cancellation_requested FROM agent_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return bool(row and row[0])

    async def get(self, owner_id: str, run_id: str) -> AgentRunRecord | None:
        async with self._lock:
            row = self._connection.execute(
                "SELECT * FROM agent_runs WHERE owner_id=? AND run_id=?", (owner_id, run_id)
            ).fetchone()
        return _run_from_row(row) if row else None

    async def list_events(
        self, owner_id: str, run_id: str, *, after: int = 0, limit: int = 200
    ) -> tuple[RunEventRecord, ...] | None:
        async with self._lock:
            owner = self._connection.execute(
                "SELECT 1 FROM agent_runs WHERE owner_id=? AND run_id=?", (owner_id, run_id)
            ).fetchone()
            if owner is None:
                return None
            rows = self._connection.execute(
                """SELECT * FROM agent_run_events WHERE run_id=? AND sequence>?
                ORDER BY sequence LIMIT ?""",
                (run_id, after, max(1, min(limit, 500))),
            ).fetchall()
        return tuple(_event_from_row(row) for row in rows)

    async def get_checkpoint(
        self, owner_id: str, run_id: str
    ) -> RunCheckpointRecord | None:
        async with self._lock:
            row = self._connection.execute(
                """SELECT checkpoint.* FROM agent_run_checkpoints AS checkpoint
                JOIN agent_runs AS run ON run.run_id=checkpoint.run_id
                WHERE run.owner_id=? AND checkpoint.run_id=?""",
                (owner_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return RunCheckpointRecord(
            run_id=row["run_id"],
            stage=row["stage"],
            runtime_phase=row["runtime_phase"],
            step=row["step"],
            state=json.loads(row["state_json"]),
            version=row["version"],
            created_at=row["created_at"],
        )

    def _get_row(self, run_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM agent_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown run: {run_id}")
        return row

    def _append_event_locked(
        self,
        run_id: str,
        *,
        event_type: str,
        stage: str | None,
        runtime_phase: str | None,
        step: int,
        data: dict[str, Any],
    ) -> None:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM agent_run_events WHERE run_id=?",
            (run_id,),
        ).fetchone()
        self._connection.execute(
            "INSERT INTO agent_run_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                int(row[0]),
                event_type,
                stage,
                runtime_phase,
                step,
                json.dumps(data, ensure_ascii=False, default=str),
                _now(),
            ),
        )

    def _save_checkpoint_locked(
        self,
        run_id: str,
        stage: str | None,
        runtime_phase: str | None,
        step: int,
        state: dict[str, Any],
    ) -> None:
        current = self._get_row(run_id)
        self._connection.execute(
            """INSERT INTO agent_run_checkpoints VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                stage=excluded.stage,
                runtime_phase=excluded.runtime_phase,
                step=excluded.step,
                state_json=excluded.state_json,
                version=excluded.version,
                created_at=excluded.created_at""",
            (
                run_id,
                stage or current["stage"],
                runtime_phase or current["runtime_phase"],
                step,
                json.dumps(state, ensure_ascii=False, default=str),
                current["version"],
                _now(),
            ),
        )

    def close(self) -> None:
        self._connection.close()


def _run_from_row(row: sqlite3.Row) -> AgentRunRecord:
    return AgentRunRecord(
        run_id=row["run_id"],
        owner_id=row["owner_id"],
        conversation_id=row["conversation_id"],
        session_id=row["session_id"],
        objective=row["objective"],
        status=row["status"],
        stage=AgentStage(row["stage"]),
        runtime_phase=row["runtime_phase"],
        step=row["step"],
        version=row["version"],
        cancellation_requested=bool(row["cancellation_requested"]),
        result_json=json.loads(row["result_json"]),
        error_json=json.loads(row["error_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _event_from_row(row: sqlite3.Row) -> RunEventRecord:
    return RunEventRecord(
        sequence=row["sequence"],
        event_type=row["event_type"],
        stage=row["stage"],
        runtime_phase=row["runtime_phase"],
        step=row["step"],
        data=json.loads(row["data_json"]),
        created_at=row["created_at"],
    )
