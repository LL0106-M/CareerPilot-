import subprocess
import sys


def test_agent_base_can_import_without_harness_runtime_cycle() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import careerpilot.agent.base"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
