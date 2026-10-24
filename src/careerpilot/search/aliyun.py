import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource


class AliyunWebSearchError(RuntimeError):
    """A sanitized Alibaba Cloud search failure safe to surface to the agent layer."""


class AliyunWebSearchProvider:
    _PATH = "/services/aigc/multimodal-generation/generation"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 45.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def search(
        self,
        query: str,
        strategy: SearchStrategy = SearchStrategy.TURBO,
    ) -> WebSearchResponse:
        payload = self._request_payload(query, strategy)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "enable",
        }
        try:
            if self._client is not None:
                return await self._stream_search(self._client, payload, headers, strategy)
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                return await self._stream_search(client, payload, headers, strategy)
        except httpx.HTTPStatusError as exc:
            raise AliyunWebSearchError(
                f"Alibaba Cloud web search failed with status {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise AliyunWebSearchError("Alibaba Cloud web search is unavailable") from exc

    def _request_payload(self, query: str, strategy: SearchStrategy) -> dict[str, Any]:
        return {
            "model": self._model,
            "input": {"messages": [{"role": "user", "content": query}]},
            "parameters": {
                "enable_search": True,
                "incremental_output": True,
                "result_format": "message",
                "search_options": {
                    "enable_source": True,
                    "forced_search": True,
                    "search_strategy": strategy.value,
                },
            },
        }

    async def _stream_search(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        headers: dict[str, str],
        strategy: SearchStrategy,
    ) -> WebSearchResponse:
        answer_parts: list[str] = []
        sources: list[WebSearchSource] = []
        seen_urls: set[str] = set()
        request_id: str | None = None
        partial = False

        async with client.stream(
            "POST",
            f"{self._base_url}{self._PATH}",
            json=payload,
            headers=headers,
            timeout=self._timeout_seconds,
        ) as response:
            response.raise_for_status()
            async for event in _data_events(response.aiter_lines()):
                try:
                    body = json.loads(event)
                except json.JSONDecodeError:
                    partial = True
                    continue
                if not isinstance(body, dict):
                    partial = True
                    continue
                if body.get("code"):
                    raise AliyunWebSearchError("Alibaba Cloud web search returned an API error")
                candidate_request_id = body.get("request_id")
                if isinstance(candidate_request_id, str):
                    request_id = candidate_request_id
                output = body.get("output")
                if not isinstance(output, dict):
                    partial = True
                    continue
                for item in _source_items(output):
                    source = _parse_source(item)
                    if source is None:
                        partial = True
                        continue
                    if source.url not in seen_urls:
                        sources.append(source)
                        seen_urls.add(source.url)
                text = _choice_text(output)
                if text:
                    answer_parts.append(text)

        if not sources:
            partial = True
        return WebSearchResponse(
            answer="".join(answer_parts).strip(),
            sources=tuple(sources),
            strategy=strategy,
            request_id=request_id,
            partial=partial,
        )


async def _data_events(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    async for line in lines:
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        data = stripped.removeprefix("data:").strip()
        if data and data != "[DONE]":
            yield data


def _source_items(output: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    search_info = output.get("search_info")
    if not isinstance(search_info, dict):
        return ()
    raw_sources = search_info.get("search_results")
    if not isinstance(raw_sources, list):
        return ()
    return tuple(item for item in raw_sources if isinstance(item, dict))


def _parse_source(item: dict[str, Any]) -> WebSearchSource | None:
    raw_url = item.get("url")
    if not isinstance(raw_url, str):
        return None
    url = _normalize_url(raw_url)
    if url is None:
        return None
    title = item.get("title")
    site_name = item.get("site_name", item.get("siteName"))
    index = item.get("index")
    raw_snippet = item.get("snippet", item.get("content", item.get("text")))
    return WebSearchSource(
        url=url,
        title=title if isinstance(title, str) and title.strip() else url,
        site_name=site_name if isinstance(site_name, str) else None,
        index=index if isinstance(index, int) else None,
        snippet=(
            raw_snippet.strip()
            if isinstance(raw_snippet, str) and raw_snippet.strip()
            else None
        ),
    )


def _normalize_url(raw_url: str) -> str | None:
    parts = urlsplit(raw_url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return None
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, "")
    )


def _choice_text(output: dict[str, Any]) -> str:
    choices = output.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)
