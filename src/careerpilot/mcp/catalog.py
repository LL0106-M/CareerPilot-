from __future__ import annotations

import re
from collections.abc import Iterable

from careerpilot.mcp.models import McpToolDescriptor

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]+", re.IGNORECASE)


def _tokens(value: str) -> frozenset[str]:
    return frozenset(match.casefold() for match in _TOKEN_PATTERN.findall(value))


class McpToolCatalog:
    """Deterministically select a small relevant MCP tool subset for one turn."""

    def select(
        self,
        query: str,
        descriptors: Iterable[McpToolDescriptor],
        *,
        limit: int = 8,
    ) -> tuple[McpToolDescriptor, ...]:
        if limit < 1:
            return ()
        normalized_query = query.strip().casefold()
        query_tokens = _tokens(normalized_query)
        if not query_tokens:
            return ()

        unique: dict[str, McpToolDescriptor] = {}
        for descriptor in descriptors:
            unique.setdefault(descriptor.namespaced_name, descriptor)

        ranked: list[tuple[int, str, McpToolDescriptor]] = []
        for namespaced_name, descriptor in unique.items():
            score = self._score(normalized_query, query_tokens, descriptor)
            if score > 0:
                ranked.append((score, namespaced_name, descriptor))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return tuple(item[2] for item in ranked[:limit])

    @staticmethod
    def _score(
        normalized_query: str,
        query_tokens: frozenset[str],
        descriptor: McpToolDescriptor,
    ) -> int:
        score = 0
        if descriptor.tool_name.casefold() in normalized_query:
            score += 100
        score += 12 * len(query_tokens & _tokens(descriptor.tool_name))
        score += 6 * len(query_tokens & _tokens(descriptor.title or ""))
        score += 3 * len(query_tokens & _tokens(descriptor.description))
        score += len(query_tokens & _tokens(descriptor.server_description))
        return score
