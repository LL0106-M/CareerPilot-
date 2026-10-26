from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def request(base_url: str, path: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=10) as response:
            return response.status, response.headers.get_content_type(), response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get_content_type(), exc.read().decode()


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a deployed CareerPilot service")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()

    health = request(args.base_url, "/health")
    ready = request(args.base_url, "/ready")
    root = request(args.base_url, "/")
    deep_link = request(args.base_url, "/chat")
    missing_api = request(args.base_url, "/v1/does-not-exist")

    assert health[0] == 200 and json.loads(health[2])["status"] == "ok", health
    assert ready[0] == 200 and json.loads(ready[2])["status"] == "ready", ready
    assert root[0] == 200 and "text/html" in root[1], root
    assert deep_link[0] == 200 and "text/html" in deep_link[1], deep_link
    assert missing_api[0] == 404 and "application/json" in missing_api[1], missing_api
    print("CareerPilot deployment smoke test passed")


if __name__ == "__main__":
    main()
