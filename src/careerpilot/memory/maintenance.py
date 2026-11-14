from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime


class MemoryMaintenanceService:
    """Consolidates projections while preserving sources and disagreement."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def consolidate(self, owner_id: str) -> dict[str, int]:
        rows = self._connection.execute(
            """SELECT * FROM conversation_episodes
            WHERE owner_id = ? AND status = 'active'
            ORDER BY created_at, id""",
            (owner_id,),
        ).fetchall()
        groups: dict[tuple[str, str, str, str], list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            groups[
                (
                    str(row["thread_id"] or ""),
                    str(row["event_kind"]),
                    self._normalize(str(row["title"])),
                    self._normalize(str(row["summary"])),
                )
            ].append(row)

        archived = 0
        now = datetime.now(UTC).isoformat()
        with self._connection:
            for duplicates in groups.values():
                if len(duplicates) < 2:
                    continue
                canonical, *redundant = duplicates
                source_ids: list[str] = []
                for row in duplicates:
                    for turn_id in json.loads(str(row["source_turn_ids_json"])):
                        if turn_id not in source_ids:
                            source_ids.append(turn_id)
                self._connection.execute(
                    """UPDATE conversation_episodes
                    SET source_turn_ids_json = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?""",
                    (json.dumps(source_ids, ensure_ascii=False), now, owner_id, canonical["id"]),
                )
                for row in redundant:
                    self._connection.execute(
                        """UPDATE conversation_episodes
                        SET status = 'archived', updated_at = ?
                        WHERE owner_id = ? AND id = ?""",
                        (now, owner_id, row["id"]),
                    )
                    self._connection.execute(
                        """UPDATE open_loops SET status = 'dismissed', updated_at = ?
                        WHERE owner_id = ? AND episode_id = ? AND status = 'active'""",
                        (now, owner_id, row["id"]),
                    )
                    archived += 1
        return {"episodes_archived": archived}

    def invalidate_source_turn(self, owner_id: str, turn_id: str) -> dict[str, int]:
        clean_turn_id = turn_id.strip()
        if not clean_turn_id:
            raise ValueError("turn_id must not be empty")
        now = datetime.now(UTC).isoformat()
        evidence_archived = 0
        episodes_archived = 0
        episodes_updated = 0
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE career_evidence SET status = 'archived', updated_at = ?
                WHERE owner_id = ? AND source_reference = ? AND status != 'archived'""",
                (now, owner_id, f"turn:{clean_turn_id}"),
            )
            evidence_archived = cursor.rowcount
            episodes = self._connection.execute(
                """SELECT id, source_turn_ids_json FROM conversation_episodes
                WHERE owner_id = ? AND status = 'active'""",
                (owner_id,),
            ).fetchall()
            for episode in episodes:
                sources = json.loads(str(episode["source_turn_ids_json"]))
                if clean_turn_id not in sources:
                    continue
                remaining = [item for item in sources if item != clean_turn_id]
                if remaining:
                    self._connection.execute(
                        """UPDATE conversation_episodes
                        SET source_turn_ids_json = ?, updated_at = ?
                        WHERE owner_id = ? AND id = ?""",
                        (
                            json.dumps(remaining, ensure_ascii=False),
                            now,
                            owner_id,
                            episode["id"],
                        ),
                    )
                    episodes_updated += 1
                    continue
                self._connection.execute(
                    """UPDATE conversation_episodes
                    SET status = 'archived', updated_at = ?
                    WHERE owner_id = ? AND id = ?""",
                    (now, owner_id, episode["id"]),
                )
                self._connection.execute(
                    """UPDATE open_loops SET status = 'dismissed', updated_at = ?
                    WHERE owner_id = ? AND episode_id = ? AND status = 'active'""",
                    (now, owner_id, episode["id"]),
                )
                episodes_archived += 1
        return {
            "evidence_archived": evidence_archived,
            "episodes_archived": episodes_archived,
            "episodes_updated": episodes_updated,
        }

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.split()).casefold()

