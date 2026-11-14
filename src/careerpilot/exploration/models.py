from __future__ import annotations

from dataclasses import dataclass

NODE_TYPES = frozenset(
    {
        "domain",
        "role_family",
        "role",
        "organization_context",
        "organization",
        "business_context",
        "location_context",
        "target",
    }
)

RELATION_TYPES = frozenset(
    {
        "contains",
        "specializes_to",
        "adjacent_to",
        "same_work_different_name",
        "possible_transition",
        "contextualized_as",
    }
)

EVIDENCE_KINDS = frozenset({"support", "counter", "unknown"})


@dataclass(frozen=True, slots=True)
class ExplorationProjection:
    thread_id: str
    focus_node_id: str | None
