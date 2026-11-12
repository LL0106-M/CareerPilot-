import json

import httpx
import pytest

from careerpilot.memory.base import MemoryRetrievalMode, MemoryStoreError
from careerpilot.memory.memos import MemosCloudMemoryStore


@pytest.mark.asyncio
async def test_search_sends_user_scope_and_parses_facts_and_preferences() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Token test-secret"
        assert json.loads(request.content) == {
            "query": "我现在更看重稳定吗？",
            "user_id": "user-1",
            "conversation_id": "thread-1",
            "relativity": 0.6,
            "memory_limit_number": 5,
            "include_memory_view": ["detail_factual", "preference"],
            "preference_limit_number": 4,
            "filter": {
                "user": {
                    "and": [
                        {"tags": {"contains": "careerpilot"}},
                        {"scene": "career_companion"},
                    ]
                }
            },
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
        assert store.enabled is True
        result = await store.search("user-1", "thread-1", "我现在更看重稳定吗？")

    assert [item.content for item in result.facts] == ["用户更看重可预期的工作节奏"]
    assert [item.content for item in result.preferences] == ["受挫时先倾听，不立即给计划"]
    assert result.facts[0].relevance == 0.91


@pytest.mark.asyncio
async def test_companion_search_broadens_recall_for_context_and_support_preferences() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["relativity"] == 0.45
        assert payload["memory_limit_number"] == 8
        assert payload["preference_limit_number"] == 8
        return httpx.Response(200, json={"code": 0, "message": "ok", "data": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = MemosCloudMemoryStore("test-secret", http_client=client)
        await store.search(
            "user-1",
            "thread-1",
            "我今天很难受",
            mode=MemoryRetrievalMode.COMPANION,
        )


@pytest.mark.asyncio
async def test_write_claim_sends_only_canonical_claim_with_local_mapping_metadata() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["user_id"] == "user-1"
        assert payload["conversation_id"] == "thread-1"
        assert payload["agent_id"] == "careerpilot"
        assert payload["app_id"] == "careerpilot-web"
        assert payload["tags"] == ["careerpilot", "active"]
        assert payload["info"]["scene"] == "career_companion"
        assert payload["info"]["memory_authority"] == "careerpilot_governed"
        assert payload["info"]["local_memory_id"] == "local-1"
        assert payload["info"]["schema_version"] == 1
        assert payload["allow_public"] is False
        assert payload["messages"] == [
            {"role": "user", "content": "偏好：受挫时先倾听"},
            {"role": "assistant", "content": "已记录这条经确认的长期记忆。"},
        ]
        assert "我今天被拒了" not in request.content.decode()
        assert "原始助手回复" not in request.content.decode()
        return httpx.Response(200, json={"code": 0, "message": "ok", "data": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = MemosCloudMemoryStore("test-secret", http_client=client)
        await store.write_claim(
            user_id="user-1",
            conversation_id="thread-1",
            local_memory_id="local-1",
            content="偏好：受挫时先倾听",
            memory_type="preference",
        )


@pytest.mark.asyncio
async def test_delete_memories_targets_exact_provider_ids() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/delete/memory")
        assert json.loads(request.content) == {
            "user_id": "user-1",
            "memory_ids": ["provider-1", "provider-2"],
        }
        return httpx.Response(200, json={"code": 0, "message": "ok", "data": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = MemosCloudMemoryStore("test-secret", http_client=client)
        await store.delete_memories("user-1", ("provider-1", "provider-2"))


@pytest.mark.asyncio
async def test_search_raises_domain_error_on_memos_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "unavailable"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        store = MemosCloudMemoryStore("test-secret", http_client=client)

        with pytest.raises(MemoryStoreError, match="MemOS search failed"):
            await store.search("user-1", "thread-1", "test")
