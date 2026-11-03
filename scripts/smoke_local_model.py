from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


class SmokeError(RuntimeError):
    pass


def _request_json(
    url: str,
    *,
    timeout_seconds: float,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise SmokeError(f"Expected a JSON object from {url}")
    return decoded


def verify_local_model(
    *,
    base_url: str,
    model: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    endpoint = base_url.rstrip("/")
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        remaining = max(0.01, deadline - time.monotonic())
        try:
            health = _request_json(
                f"{endpoint}/health",
                timeout_seconds=min(5.0, remaining),
            )
            if health.get("status") == "ok":
                break
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            last_error = exc
        time.sleep(min(poll_interval_seconds, max(0.0, deadline - time.monotonic())))
    else:
        detail = f": {last_error}" if last_error is not None else ""
        raise SmokeError(f"Local model did not become ready within {timeout_seconds:g}s{detail}")

    models = _request_json(f"{endpoint}/models", timeout_seconds=5.0)
    model_ids = {
        item.get("id")
        for item in models.get("data", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if model not in model_ids:
        raise SmokeError(f"Expected model {model!r}; server reported {sorted(model_ids)!r}")

    completion = _request_json(
        f"{endpoint}/chat/completions",
        timeout_seconds=max(30.0, timeout_seconds),
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "请只回复：本地模型已连接"}],
            "temperature": 0,
            "max_tokens": 32,
        },
    )
    choices = completion.get("choices")
    if not isinstance(choices, list) or not choices:
        raise SmokeError("Chat completion returned no choices")
    first = choices[0]
    if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
        raise SmokeError("Chat completion returned an invalid message")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a local OpenAI-compatible model")
    parser.add_argument("--base-url", default="http://127.0.0.1:8081/v1")
    parser.add_argument("--model", default="Qwen3-4B-GGUF")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        verify_local_model(
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )
    except (SmokeError, OSError, ValueError) as exc:
        print(f"Local model smoke test failed: {exc}", file=sys.stderr)
        return 1
    print("Local model smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
