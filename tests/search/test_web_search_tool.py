import json
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource
from careerpilot.search.tool import build_web_search_tool


@dataclass
class RecordingSearchProvider:
    calls: list[tuple[str, SearchStrategy]] = field(default_factory=list)

    async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse:
        self.calls.append((query, strategy))
        return WebSearchResponse(
            answer="发现近期岗位。",
            sources=(
                WebSearchSource(
                    url="https://jobs.example.com/agent-pm",
                    title="Agent 产品经理",
                    site_name="Example Jobs",
                    index=1,
                ),
            ),
            strategy=strategy,
            request_id="req-1",
        )


@pytest.mark.asyncio
async def test_web_search_tool_returns_untrusted_traceable_evidence() -> None:
    provider = RecordingSearchProvider()
    tool = build_web_search_tool(provider)

    raw = await tool.ainvoke({"query": "近期 Agent 产品岗位", "strategy": "max"})
    result = json.loads(raw)

    assert provider.calls == [("近期 Agent 产品岗位", SearchStrategy.MAX)]
    assert result == {
        "status": "available",
        "content_is_untrusted": True,
        "strategy": "max",
        "partial": False,
        "request_id": "req-1",
        "answer": "发现近期岗位。",
        "sources": [
            {
                "index": 1,
                "title": "Agent 产品经理",
                "url": "https://jobs.example.com/agent-pm",
                "site_name": "Example Jobs",
            }
        ],
    }


@pytest.mark.asyncio
async def test_web_search_tool_rejects_nested_agent_strategy() -> None:
    tool = build_web_search_tool(RecordingSearchProvider())

    with pytest.raises(ValidationError):
        await tool.ainvoke({"query": "query", "strategy": "agent"})
