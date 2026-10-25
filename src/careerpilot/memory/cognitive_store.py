import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from careerpilot.memory.daily_review import DailyReview
from careerpilot.memory.dreaming import (
    CareerHypothesis,
    DreamingAnalysis,
    DreamingJob,
    DreamingSnapshot,
    DreamingTrigger,
    EvidenceRef,
    HypothesisProposal,
)


@dataclass(frozen=True, slots=True)
class StoredMemoryPatch:
    id: str
    owner_id: str
    operation: str
    target_type: str
    content: str
    supporting_evidence_ids: tuple[str, ...]
    requires_confirmation: bool
    status: str


class SqliteCognitiveStore:
    """Deterministic state for Dreaming jobs and non-factual career hypotheses."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
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

            CREATE TABLE IF NOT EXISTS daily_reviews (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                local_date TEXT NOT NULL,
                wins_json TEXT NOT NULL,
                ideas_json TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                open_loops_json TEXT NOT NULL,
                tomorrow_step TEXT,
                source_event_ids_json TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner_id, local_date)
            );

            CREATE TABLE IF NOT EXISTS memory_patch_candidates (
                id TEXT PRIMARY KEY,
                dreaming_job_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                target_type TEXT NOT NULL,
                content TEXT NOT NULL,
                supporting_evidence_json TEXT NOT NULL,
                requires_confirmation INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        self.complete_analysis(job, DreamingAnalysis(hypotheses=proposals))

    def complete_analysis(self, job: DreamingJob, analysis: DreamingAnalysis) -> None:
        proposals = analysis.hypotheses
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

        for patch in analysis.patches:
            if not patch.content.strip() or not patch.supporting_evidence_ids:
                raise ValueError("Dreaming patch requires content and supporting evidence")
            if not set(patch.supporting_evidence_ids) <= allowed_evidence:
                raise ValueError("Dreaming patch cites evidence outside its snapshot")
        if analysis.daily_review is not None:
            if not set(analysis.daily_review.source_event_ids) <= allowed_evidence:
                raise ValueError("Dreaming daily review cites evidence outside its snapshot")

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
            if analysis.daily_review is not None:
                review = analysis.daily_review
                existing = self._connection.execute(
                    "SELECT id, version FROM daily_reviews WHERE owner_id=? AND local_date=?",
                    (job.snapshot.user_id, review.local_date),
                ).fetchone()
                if existing is None:
                    self._connection.execute(
                        """INSERT INTO daily_reviews (
                        id, owner_id, local_date, wins_json, ideas_json, blockers_json,
                        open_loops_json, tomorrow_step, source_event_ids_json, status, version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', 1)""",
                        (
                            str(uuid4()),
                            job.snapshot.user_id,
                            review.local_date,
                            json.dumps(review.wins, ensure_ascii=False),
                            json.dumps(review.ideas, ensure_ascii=False),
                            json.dumps(review.blockers, ensure_ascii=False),
                            json.dumps(review.open_loops, ensure_ascii=False),
                            review.tomorrow_step,
                            json.dumps(review.source_event_ids, ensure_ascii=False),
                        ),
                    )
                else:
                    self._connection.execute(
                        """UPDATE daily_reviews SET wins_json=?, ideas_json=?, blockers_json=?,
                        open_loops_json=?, tomorrow_step=?, source_event_ids_json=?,
                        version=version+1, updated_at=CURRENT_TIMESTAMP
                        WHERE owner_id=? AND local_date=?""",
                        (
                            json.dumps(review.wins, ensure_ascii=False),
                            json.dumps(review.ideas, ensure_ascii=False),
                            json.dumps(review.blockers, ensure_ascii=False),
                            json.dumps(review.open_loops, ensure_ascii=False),
                            review.tomorrow_step,
                            json.dumps(review.source_event_ids, ensure_ascii=False),
                            job.snapshot.user_id,
                            review.local_date,
                        ),
                    )
            for patch in analysis.patches:
                self._connection.execute(
                    """INSERT INTO memory_patch_candidates (
                    id, dreaming_job_id, owner_id, operation, target_type, content,
                    supporting_evidence_json, requires_confirmation, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid4()),
                        job.id,
                        job.snapshot.user_id,
                        patch.operation,
                        patch.target_type,
                        patch.content.strip(),
                        json.dumps(patch.supporting_evidence_ids, ensure_ascii=False),
                        int(patch.requires_confirmation),
                        "pending" if patch.requires_confirmation else "validated",
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

    def get_daily_review(self, owner_id: str, local_date: str) -> DailyReview | None:
        row = self._connection.execute(
            "SELECT * FROM daily_reviews WHERE owner_id=? AND local_date=?",
            (owner_id, local_date),
        ).fetchone()
        if row is None:
            return None
        return DailyReview(
            id=row["id"],
            owner_id=row["owner_id"],
            local_date=row["local_date"],
            wins=tuple(json.loads(row["wins_json"])),
            ideas=tuple(json.loads(row["ideas_json"])),
            blockers=tuple(json.loads(row["blockers_json"])),
            open_loops=tuple(json.loads(row["open_loops_json"])),
            tomorrow_step=row["tomorrow_step"],
            source_event_ids=tuple(json.loads(row["source_event_ids_json"])),
            status=row["status"],
            version=row["version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_daily_reviews(self, owner_id: str, limit: int = 30) -> tuple[DailyReview, ...]:
        rows = self._connection.execute(
            """SELECT local_date FROM daily_reviews WHERE owner_id=?
            ORDER BY local_date DESC, rowid DESC LIMIT ?""",
            (owner_id, max(1, min(limit, 100))),
        ).fetchall()
        return tuple(
            review
            for row in rows
            if (review := self.get_daily_review(owner_id, row["local_date"])) is not None
        )

    def list_memory_patches(self, owner_id: str) -> tuple[StoredMemoryPatch, ...]:
        rows = self._connection.execute(
            """SELECT * FROM memory_patch_candidates WHERE owner_id=?
            ORDER BY created_at DESC, rowid DESC""",
            (owner_id,),
        ).fetchall()
        return tuple(
            StoredMemoryPatch(
                id=row["id"],
                owner_id=row["owner_id"],
                operation=row["operation"],
                target_type=row["target_type"],
                content=row["content"],
                supporting_evidence_ids=tuple(json.loads(row["supporting_evidence_json"])),
                requires_confirmation=bool(row["requires_confirmation"]),
                status=row["status"],
            )
            for row in rows
        )

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
