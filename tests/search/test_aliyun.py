import json

import httpx
import pytest

from careerpilot.search.aliyun import AliyunWebSearchError, AliyunWebSearchProvider
from careerpilot.search.models import SearchStrategy


def _sse(*payloads: dict[str, object] | str) -> str:
    lines: list[str] = []
    for payload in payloads:
        data = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        lines.extend(("event: result", f"data: {data}", ""))
    return "\n".join(lines)


@pytest.mark.asyncio
async def test_search_sends_governed_multimodal_request_and_returns_sources() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/services/aigc/multimodal-generation/generation")
        assert request.headers["authorization"] == "Bearer test-secret"
        assert request.headers["x-dashscope-sse"] == "enable"
        body = json.loads(request.content)
        assert body == {
            "model": "qwen3.7-plus-2026-05-26",
            "input": {"messages": [{"role": "user", "content": "近期 Agent 产品岗位"}]},
            "parameters": {
                "enable_search": True,
                "incremental_output": True,
                "result_format": "message",
                "search_options": {
                    "enable_source": True,
                    "forced_search": True,
                    "search_strategy": "turbo",
                },
            },
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=_sse(
                {
                    "request_id": "req-1",
                    "output": {
                        "search_info": {
                            "search_results": [
                                {
                                    "index": 1,
                                    "title": "Agent 产品经理岗位",
                                    "url": "https://jobs.example.com/agent-pm",
                                    "site_name": "Example Jobs",
                                }
                            ]
                        },
                        "choices": [{"message": {"content": "发现一条"}}],
                    },
                },
                {
                    "request_id": "req-1",
                    "output": {"choices": [{"message": {"content": "相关岗位。"}}]},
                },
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AliyunWebSearchProvider(
            api_key="test-secret",
            base_url="https://workspace.example.com/api/v1/",
            model="qwen3.7-plus-2026-05-26",
            client=client,
        )
        response = await provider.search("近期 Agent 产品岗位", SearchStrategy.TURBO)

    assert response.answer == "发现一条相关岗位。"
    assert response.request_id == "req-1"
    assert response.partial is False
    assert len(response.sources) == 1
    assert response.sources[0].url == "https://jobs.example.com/agent-pm"
    assert response.sources[0].site_name == "Example Jobs"


@pytest.mark.asyncio
async def test_search_skips_malformed_events_and_deduplicates_fragment_urls() -> None:
    payload = {
        "output": {
            "search_info": {
                "search_results": [
                    {"index": 1, "title": "A", "url": "https://example.com/a#first"},
                    {"index": 2, "title": "A duplicate", "url": "https://EXAMPLE.com/a#two"},
                    {"index": 3, "title": "Missing URL"},
                ]
            },
            "choices": [{"message": {"content": "answer"}}],
        }
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_sse("{not-json", payload))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AliyunWebSearchProvider(
            api_key="test-secret",
            base_url="https://workspace.example.com/api/v1",
            model="qwen3.7-plus-2026-05-26",
            client=client,
        )
        response = await provider.search("query", SearchStrategy.MAX)

    assert [source.url for source in response.sources] == ["https://example.com/a"]
    assert response.partial is True


@pytest.mark.asyncio
async def test_search_converts_http_failures_to_sanitized_domain_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "secret rejected"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AliyunWebSearchProvider(
            api_key="test-secret",
            base_url="https://workspace.example.com/api/v1",
            model="qwen3.7-plus-2026-05-26",
            client=client,
        )
        with pytest.raises(AliyunWebSearchError, match="status 401") as error:
            await provider.search("query", SearchStrategy.TURBO)

    assert "secret rejected" not in str(error.value)
    assert "test-secret" not in str(error.value)
