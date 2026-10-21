import json
import subprocess
import sys
from pathlib import Path


def test_ingest_job_records_cli_is_incremental(tmp_path: Path) -> None:
    records = [
        {
            "company_name": "示例公司",
            "role_title": "AI 产品经理",
            "locations": ["上海"],
            "source_url": "https://example.com/jobs/ai-pm",
            "source_level": "S",
            "status": "active",
        }
    ]
    input_path = tmp_path / "jobs.json"
    input_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    db_path = tmp_path / "rag.db"
    repository_root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "scripts/ingest_job_records.py",
        str(input_path),
        "--db",
        str(db_path),
        "--fetched-at",
        "2026-10-20T12:00:00+00:00",
    ]

    first = subprocess.run(command, cwd=repository_root, capture_output=True, text=True)
    second = subprocess.run(command, cwd=repository_root, capture_output=True, text=True)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(first.stdout)["indexed"] == 1
    assert json.loads(second.stdout)["unchanged"] == 1

