import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from careerpilot.harness.contracts import HarnessMessage, SessionStore, ToolCall
from careerpilot.harness.context_window import SessionCompaction


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, list[HarnessMessage]] = {}
        self._lock = asyncio.Lock()

    async def load(self, session_id: str) -> tuple[HarnessMessage, ...]:
        async with self._lock:
            return tuple(self._sessions.get(session_id, ()))

    async def append(
        self, session_id: str, messages: tuple[HarnessMessage, ...]
    ) -> None:
        async with self._lock:
            self._sessions.setdefault(session_id, []).extend(messages)


class SqliteSessionStore(SessionStore):
    """Small durable session log; product state remains in its own stores."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_messages (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_harness_messages_session "
            "ON harness_messages(session_id, sequence)"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS session_compactions (
                session_id TEXT PRIMARY KEY,
                covered_message_count INTEGER NOT NULL,
                source_hash TEXT NOT NULL,
                summary TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                model_metadata TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
        self._lock = asyncio.Lock()

    async def load(self, session_id: str) -> tuple[HarnessMessage, ...]:
        async with self._lock:
            rows = self._connection.execute(
                "SELECT payload_json FROM harness_messages "
                "WHERE session_id = ? ORDER BY sequence",
                (session_id,),
            ).fetchall()
        return tuple(_message_from_json(row[0]) for row in rows)

    async def append(
        self, session_id: str, messages: tuple[HarnessMessage, ...]
    ) -> None:
        if not messages:
            return
        async with self._lock:
            self._connection.executemany(
                "INSERT INTO harness_messages(session_id, payload_json) VALUES (?, ?)",
                [(session_id, _message_to_json(message)) for message in messages],
            )
            self._connection.commit()

    async def load_compaction(self, session_id: str) -> SessionCompaction | None:
        async with self._lock:
            row = self._connection.execute(
                "SELECT * FROM session_compactions WHERE session_id=?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return SessionCompaction(
            session_id=row["session_id"],
            covered_message_count=row["covered_message_count"],
            source_hash=row["source_hash"],
            summary=row["summary"],
            schema_version=row["schema_version"],
            model_metadata=row["model_metadata"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def save_compaction(self, compaction: SessionCompaction) -> None:
        async with self._lock:
            self._connection.execute(
                """INSERT INTO session_compactions VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    covered_message_count=excluded.covered_message_count,
                    source_hash=excluded.source_hash,
                    summary=excluded.summary,
                    schema_version=excluded.schema_version,
                    model_metadata=excluded.model_metadata,
                    created_at=excluded.created_at""",
                (
                    compaction.session_id,
                    compaction.covered_message_count,
                    compaction.source_hash,
                    compaction.summary,
                    compaction.schema_version,
                    compaction.model_metadata,
                    compaction.created_at.isoformat(),
                ),
            )
            self._connection.commit()

    def close(self) -> None:
        self._connection.close()


def _message_to_json(message: HarnessMessage) -> str:
    return json.dumps(
        {
            "role": message.role,
            "content": message.content,
            "tool_calls": [
                {"id": call.id, "name": call.name, "arguments": call.arguments}
                for call in message.tool_calls
            ],
            "tool_call_id": message.tool_call_id,
            "name": message.name,
        },
        ensure_ascii=False,
    )


def _message_from_json(payload: str) -> HarnessMessage:
    data = json.loads(payload)
    return HarnessMessage(
        role=data["role"],
        content=data.get("content", ""),
        tool_calls=tuple(ToolCall(**item) for item in data.get("tool_calls", ())),
        tool_call_id=data.get("tool_call_id"),
        name=data.get("name"),
    )
