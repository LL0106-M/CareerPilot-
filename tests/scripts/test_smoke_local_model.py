from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "smoke_local_model.py"


class _ModelHandler(BaseHTTPRequestHandler):
    health_calls = 0

    def do_GET(self) -> None:
        if self.path == "/v1/health":
            type(self).health_calls += 1
            if type(self).health_calls < 3:
                self._json(503, {"error": {"message": "Loading model"}})
            else:
                self._json(200, {"status": "ok"})
            return
        if self.path == "/v1/models":
            self._json(200, {"data": [{"id": "Qwen3-4B-GGUF"}]})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length))
        assert payload["model"] == "Qwen3-4B-GGUF"
        self._json(
            200,
            {"choices": [{"message": {"role": "assistant", "content": "你好"}}]},
        )

    def log_message(self, _format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_smoke_retries_loading_then_checks_models_and_chat() -> None:
    _ModelHandler.health_calls = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run(
            "--base-url",
            f"http://127.0.0.1:{server.server_port}/v1",
            "--timeout-seconds",
            "2",
            "--poll-interval-seconds",
            "0.01",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.returncode == 0, result.stderr
    assert "Local model smoke test passed" in result.stdout
    assert _ModelHandler.health_calls == 3


def test_smoke_reports_timeout_when_model_is_unreachable() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]

    result = _run(
        "--base-url",
        f"http://127.0.0.1:{unused_port}/v1",
        "--timeout-seconds",
        "0.05",
        "--poll-interval-seconds",
        "0.01",
    )

    assert result.returncode == 1
    assert "did not become ready" in result.stderr
