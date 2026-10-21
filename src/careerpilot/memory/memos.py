from collections.abc import Mapping
from typing import Any

import httpx

from careerpilot.memory.base import MemoryContext, MemoryItem, MemoryStoreError


class MemosCloudMemoryStore:
    """HTTP adapter for the MemOS Cloud OpenMem API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://memos.memtensor.cn/api/openmem/v1",
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        if not api_key:
            raise ValueError("MemOS API key is required")
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = http_client is None
        self._headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    async def search(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
    ) -> MemoryContext:
        payload = {
            "query": query,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "relativity": 0.55,
            "memory_limit_number": 6,
            "include_preference": True,
            "preference_limit_number": 6,
            "include_skill": False,
            "include_tool_memory": False,
        }
        result = await self._post("/search/memory", payload, operation="search")
        data = result.get("data")
        if not isinstance(data, Mapping):
            return MemoryContext()

        facts = tuple(self._parse_facts(data.get("memory_detail_list")))
        preferences = tuple(self._parse_preferences(data.get("preference_detail_list")))
        return MemoryContext(facts=facts, preferences=preferences)

    async def add_turn(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        payload = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "agent_id": "careerpilot",
            "source": "careerpilot_web",
            "allow_public": False,
            "async_mode": True,
            "tags": ["careerpilot", "candidate"],
            "info": {"scene": "career_companion", "memory_status": "candidate"},
            "messages": [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ],
        }
        await self._post("/add/message", payload, operation="write")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        operation: str,
    ) -> Mapping[str, Any]:
        try:
            response = await self._client.post(
                f"{self._base_url}{path}",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MemoryStoreError(f"MemOS {operation} failed") from exc

        if not isinstance(body, Mapping) or body.get("code") != 0:
            raise MemoryStoreError(f"MemOS {operation} failed")
        return body

    @staticmethod
    def _parse_facts(value: object) -> list[MemoryItem]:
        if not isinstance(value, list):
            return []
        items: list[MemoryItem] = []
        for raw in value:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("memory_value"), str):
                continue
            relevance = raw.get("relativity")
            items.append(
                MemoryItem(
                    id=str(raw["id"]) if raw.get("id") is not None else None,
                    content=raw["memory_value"],
                    kind=str(raw.get("memory_type", "fact")),
                    relevance=float(relevance) if isinstance(relevance, int | float) else None,
                )
            )
        return items

    @staticmethod
    def _parse_preferences(value: object) -> list[MemoryItem]:
        if not isinstance(value, list):
            return []
        items: list[MemoryItem] = []
        for raw in value:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("preference"), str):
                continue
            items.append(
                MemoryItem(
                    id=None,
                    content=raw["preference"],
                    kind=str(raw.get("preference_type", "preference")),
                )
            )
        return items
