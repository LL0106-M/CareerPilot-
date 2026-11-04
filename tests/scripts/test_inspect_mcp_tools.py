from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "inspect_mcp_tools.py"
FIXTURE = ROOT / "tests" / "mcp" / "fixtures" / "read_only_server.py"


def _run(config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(config)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def test_cli_lists_policy_visible_tools_without_invoking_them(tmp_path: Path) -> None:
    config = tmp_path / "mcp.json"
    config.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "fixture",
                        "transport": "stdio",
                        "command": sys.executable,
                        "args": [str(FIXTURE)],
                        "env": {"CAREERPILOT_FIXTURE_SCOPE": "diagnostic"},
                        "allowed_tools": ["inspect_fixture_environment"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    completed = _run(config)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["tools"][0]["name"] == (
        "mcp__fixture__inspect_fixture_environment"
    )
    assert payload["tools"][0]["read_only"] is True
    assert "diagnostic" not in completed.stdout


def test_cli_fails_safely_for_invalid_or_unavailable_config(tmp_path: Path) -> None:
    secret = "never-print-this-secret"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "bad",
                        "transport": "stdio",
                        "command": secret,
                        "env": {"TOKEN": secret},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    completed = _run(invalid)

    assert completed.returncode != 0
    assert secret not in completed.stderr
    assert "MCP inspection failed" in completed.stderr
