import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from careerpilot.memory.dreaming import (
    CareerHypothesis,
    DreamingJob,
    DreamingSnapshot,
    DreamingTrigger,
    EvidenceRef,
    HypothesisProposal,
)


class SqliteCognitiveStore:
    """Deterministic state for Dreaming jobs and non-factual career hypotheses."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS dreaming_jobs (
                id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS career_hypotheses (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                statement TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status = 'candidate'),
                confidence_band TEXT NOT NULL,
                supporting_evidence_json TEXT NOT NULL,
                contradicting_evidence_json TEXT NOT NULL,
                open_questions_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, statement, status)
            );
            """
        )
        self._connection.commit()

    def enqueue(self, snapshot: DreamingSnapshot) -> bool:
        payload = self._snapshot_to_json(snapshot)
        key_material = "\n".join(
            (
                snapshot.user_id,
                snapshot.conversation_id,
                snapshot.trigger.value,
                snapshot.user_message.strip(),
            )
        )
        idempotency_key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        cursor = self._connection.execute(
            """
            INSERT OR IGNORE INTO dreaming_jobs (
                id, idempotency_key, user_id, conversation_id, trigger, status, payload_json
            ) VALUES (?, ?, ?, ?, ?, 'queued', ?)
            """,
            (
                str(uuid4()),
                idempotency_key,
                snapshot.user_id,
                snapshot.conversation_id,
                snapshot.trigger.value,
                payload,
            ),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def claim_next(self) -> DreamingJob | None:
        self._connection.execute("BEGIN IMMEDIATE")
        row = self._connection.execute(
            """
            SELECT id, payload_json, attempts
            FROM dreaming_jobs
            WHERE status = 'queued'
            ORDER BY created_at, rowid
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            self._connection.commit()
            return None
        self._connection.execute(
            """
            UPDATE dreaming_jobs
            SET status = 'processing', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'queued'
            """,
            (row["id"],),
        )
        self._connection.commit()
        return DreamingJob(
            id=row["id"],
            snapshot=self._snapshot_from_json(row["payload_json"]),
            attempts=row["attempts"],
        )

    def complete(self, job: DreamingJob, proposals: tuple[HypothesisProposal, ...]) -> None:
        allowed_evidence = {item.id for item in job.snapshot.evidence}
        for proposal in proposals:
            if not proposal.statement.strip():
                raise ValueError("Dreaming hypothesis statement cannot be empty")
            if proposal.confidence_band not in {"low", "medium", "high"}:
                raise ValueError("Dreaming confidence band is invalid")
            if not proposal.supporting_evidence_ids:
                raise ValueError("Dreaming hypothesis requires supporting evidence")
            cited = set(proposal.supporting_evidence_ids) | set(
                proposal.contradicting_evidence_ids
            )
            if not cited <= allowed_evidence:
                raise ValueError("Dreaming hypothesis cites evidence outside its snapshot")

        with self._connection:
            for proposal in proposals:
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO career_hypotheses (
                        id, user_id, statement, status, confidence_band,
                        supporting_evidence_json, contradicting_evidence_json,
                        open_questions_json
                    ) VALUES (?, ?, ?, 'candidate', ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        job.snapshot.user_id,
                        proposal.statement.strip(),
                        proposal.confidence_band,
                        json.dumps(proposal.supporting_evidence_ids, ensure_ascii=False),
                        json.dumps(proposal.contradicting_evidence_ids, ensure_ascii=False),
                        json.dumps(proposal.open_questions, ensure_ascii=False),
                    ),
                )
            updated = self._connection.execute(
                """
                UPDATE dreaming_jobs
                SET status = 'completed', last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'processing'
                """,
                (job.id,),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Dreaming job is not processing")

    def fail(self, job: DreamingJob, error: str) -> None:
        self._connection.execute(
            """
            UPDATE dreaming_jobs
            SET status = CASE WHEN attempts + 1 >= 3 THEN 'failed' ELSE 'queued' END,
                attempts = attempts + 1, last_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'processing'
            """,
            (error[:200], job.id),
        )
        self._connection.commit()

    def list_hypotheses(
        self, user_id: str, limit: int = 5
    ) -> tuple[CareerHypothesis, ...]:
        rows = self._connection.execute(
            """
            SELECT * FROM career_hypotheses
            WHERE user_id = ? AND status = 'candidate'
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return tuple(
            CareerHypothesis(
                id=row["id"],
                user_id=row["user_id"],
                statement=row["statement"],
                status=row["status"],
                confidence_band=row["confidence_band"],
                supporting_evidence_ids=tuple(json.loads(row["supporting_evidence_json"])),
                contradicting_evidence_ids=tuple(
                    json.loads(row["contradicting_evidence_json"])
                ),
                open_questions=tuple(json.loads(row["open_questions_json"])),
            )
            for row in rows
        )

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _snapshot_to_json(snapshot: DreamingSnapshot) -> str:
        payload = asdict(snapshot)
        payload["trigger"] = snapshot.trigger.value
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _snapshot_from_json(value: str) -> DreamingSnapshot:
        payload = json.loads(value)
        return DreamingSnapshot(
            user_id=payload["user_id"],
            conversation_id=payload["conversation_id"],
            trigger=DreamingTrigger(payload["trigger"]),
            user_message=payload["user_message"],
            assistant_message=payload["assistant_message"],
            evidence=tuple(EvidenceRef(**item) for item in payload["evidence"]),
        )
