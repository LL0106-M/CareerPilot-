import json

import httpx
import pytest

from careerpilot.memory.base import MemoryStoreError
from careerpilot.memory.memos import MemosCloudMemoryStore


@pytest.mark.asyncio
async def test_search_sends_user_scope_and_parses_facts_and_preferences() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Token test-secret"
        assert json.loads(request.content) == {
            "query": "我现在更看重稳定吗？",
            "user_id": "user-1",
            "conversation_id": "thread-1",
            "relativity": 0.55,
            "memory_limit_number": 6,
            "include_preference": True,
            "preference_limit_number": 6,
            "include_skill": False,
            "include_tool_memory": False,
        }
        return httpx.Response(
            200,
            json={
                "code": 0,
                "message": "ok",
                "data": {
                    "memory_detail_list": [
                        {
                            "id": "memory-1",
                            "memory_value": "用户更看重可预期的工作节奏",
                            "memory_type": "LongTermMemory",
                            "relativity": 0.91,
                        }
                    ],
                    "preference_detail_list": [
                        {
                            "preference_type": "explicit_preference",
                            "preference": "受挫时先倾听，不立即给计划",
                        }
                    ],
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = MemosCloudMemoryStore("test-secret", http_client=client)
        result = await store.search("user-1", "thread-1", "我现在更看重稳定吗？")

    assert [item.content for item in result.facts] == ["用户更看重可预期的工作节奏"]
    assert [item.content for item in result.preferences] == ["受挫时先倾听，不立即给计划"]
    assert result.facts[0].relevance == 0.91


@pytest.mark.asyncio
async def test_add_turn_uses_private_agent_scoped_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["user_id"] == "user-1"
        assert payload["conversation_id"] == "thread-1"
        assert payload["agent_id"] == "careerpilot"
        assert payload["allow_public"] is False
        assert payload["messages"] == [
            {"role": "user", "content": "我希望先被理解"},
            {"role": "assistant", "content": "我先陪你把难受放下来。"},
        ]
        return httpx.Response(200, json={"code": 0, "message": "ok", "data": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = MemosCloudMemoryStore("test-secret", http_client=client)
        await store.add_turn(
            user_id="user-1",
            conversation_id="thread-1",
            user_message="我希望先被理解",
            assistant_message="我先陪你把难受放下来。",
        )


@pytest.mark.asyncio
async def test_search_raises_domain_error_on_memos_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "unavailable"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = MemosCloudMemoryStore("test-secret", http_client=client)

        with pytest.raises(MemoryStoreError, match="MemOS search failed"):
            await store.search("user-1", "thread-1", "test")
