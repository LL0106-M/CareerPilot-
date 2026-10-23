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
        self._seed(owner_id)
        return {
            "hypotheses": self._rows("hypotheses", owner_id, "id"),
            "journey": self._rows("journey_tasks", owner_id, "rowid"),
            "memories": self._rows("memories", owner_id, "rowid"),
            "dreaming": self._rows("dreaming_insights", owner_id, "rowid DESC"),
        }

    def decide_hypothesis(self, owner_id: str, hypothesis_id: str, decision: str) -> bool:
        self._seed(owner_id)
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
        self._seed(owner_id)
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
        self._seed(owner_id)
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

    def _seed(self, owner_id: str) -> None:
        exists = self._connection.execute(
            "SELECT 1 FROM hypotheses WHERE owner_id = ? LIMIT 1", (owner_id,)
        ).fetchone()
        if exists:
            return
        hypotheses = [
            (
                "hyp-001",
                "你可能更适合有明确边界，但仍能参与产品创造的工作环境。",
                "中",
                "待确认",
                ["近期更关注稳定岗位", "仍持续投入 AI 产品项目", "明确不喜欢完全重复的工作"],
                "environment",
            ),
            (
                "hyp-002",
                "你在真实项目中形成判断，比单纯阅读职业介绍更有效。",
                "高",
                "继续观察",
                ["作品集项目后职业描述明显具体", "两次实践复盘产生了新的岗位问题"],
                "strengths",
            ),
        ]
        self._connection.executemany(
            "INSERT INTO hypotheses VALUES (?,?,?,?,?,?,?)",
            [
                (
                    owner_id,
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    json.dumps(item[4], ensure_ascii=False),
                    item[5],
                )
                for item in hypotheses
            ],
        )
        tasks = [
            (
                "task-001",
                "完成中国移动岗位要求拆解",
                "今天",
                "进行中",
                "中国移动｜产品运营管理",
                "hyp-001",
                "验证稳定组织中的产品工作是否仍保留创造空间。",
            ),
            (
                "task-002",
                "准备一个 AI 项目失败复盘",
                "明天",
                "准备开始",
                "腾讯｜AI 产品经理",
                "hyp-002",
                "验证真实项目复盘能否更好展示你的判断力。",
            ),
            (
                "task-003",
                "记录这周对工作节奏的观察",
                "周日",
                "准备开始",
                "职业偏好验证",
                "hyp-001",
                "用真实体验判断你能持续接受的工作节奏。",
            ),
        ]
        self._connection.executemany(
            "INSERT INTO journey_tasks VALUES (?,?,?,?,?,?,?,?,NULL)",
            [(owner_id, *item) for item in tasks],
        )
        memories = [
            (
                "mem-001",
                "偏好",
                "想去做和环境保护相关的工作",
                "对话确认",
                "10 月 12 日",
                "interests",
            ),
            ("mem-002", "情绪", "担心自己不够优秀", "对话观察", "10 月 5 日", "risks"),
            ("mem-003", "事实", "安静的环境能让我更专注", "用户确认", "9 月 28 日", "environment"),
        ]
        self._connection.executemany(
            "INSERT INTO memories VALUES (?,?,?,?,?,?,?)",
            [(owner_id, *item) for item in memories],
        )
        details = {
            "认知更新": "稳定感与创造性可能不是二选一，你更在意的是边界清楚且能参与创造。",
            "情绪观察": "当准备事项不断增加时，你更容易担心自己还不够好。",
            "下一步建议": "选一个真实岗位，用 30 分钟核对工作节奏和创造空间。",
        }
        self._connection.execute(
            "INSERT INTO dreaming_insights VALUES (?,?,?,?,?,?,?)",
            (
                owner_id,
                "dream-001",
                "今天 02:10",
                "在自然与创意之间找到结合点",
                "从你最近的记录来看，你对既有意义又适合自己的方向出现得更频繁了。",
                "待查看",
                json.dumps(details, ensure_ascii=False),
            ),
        )
        self._connection.commit()
