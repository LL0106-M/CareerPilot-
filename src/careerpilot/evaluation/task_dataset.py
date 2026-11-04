from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCENARIOS = frozenset(
    {
        "emotional_clarification",
        "career_exploration",
        "external_research",
        "action_execution",
        "long_term_review",
    }
)
TASK_TYPES = frozenset({"single_turn", "multi_turn", "long_horizon"})
DETERMINISTIC_GRADERS = frozenset({"rule", "trace", "state"})
SEED_SCENARIO_QUOTA = {scenario: 4 for scenario in SCENARIOS}
SEED_TASK_TYPE_QUOTA = {"single_turn": 8, "multi_turn": 7, "long_horizon": 5}


@dataclass(frozen=True, slots=True)
class TaskCase:
    schema_version: str
    task_id: str
    name: str
    business_scenario: str
    task_type: str
    capability_tags: tuple[str, ...]
    complexity_tags: tuple[str, ...]
    user_profile: dict[str, Any]
    initial_state: dict[str, Any]
    environment: dict[str, Any]
    turns: tuple[dict[str, Any], ...]
    expected_outcome: dict[str, Any]
    graders: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TaskCase:
        required = (
            "schema_version",
            "task_id",
            "name",
            "business_scenario",
            "task_type",
            "capability_tags",
            "complexity_tags",
            "user_profile",
            "initial_state",
            "environment",
            "turns",
            "expected_outcome",
            "graders",
            "metadata",
        )
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

        task_id = str(payload["task_id"]).strip()
        if not task_id:
            raise ValueError("task_id must not be empty")
        if payload["schema_version"] != "2.0":
            raise ValueError("schema_version must be 2.0")

        scenario = str(payload["business_scenario"])
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown business_scenario: {scenario}")
        task_type = str(payload["task_type"])
        if task_type not in TASK_TYPES:
            raise ValueError(f"unknown task_type: {task_type}")

        capability_tags = _string_tuple(payload["capability_tags"], "capability_tags")
        complexity_tags = _string_tuple(payload["complexity_tags"], "complexity_tags")
        turns = _mapping_tuple(payload["turns"], "turns")
        if not turns:
            raise ValueError("turns must contain at least one turn")
        graders = _mapping_tuple(payload["graders"], "graders")
        if not any(str(grader.get("type")) in DETERMINISTIC_GRADERS for grader in graders):
            raise ValueError("at least one deterministic grader is required")

        expected_outcome = _dict(payload["expected_outcome"], "expected_outcome")
        hard_failures = expected_outcome.get("hard_failures")
        if not isinstance(hard_failures, list) or not hard_failures:
            raise ValueError("at least one hard failure is required")

        if scenario == "action_execution":
            if "authorization_control" not in capability_tags:
                raise ValueError("action_execution requires authorization_control capability")
            if "unauthorized_external_write" not in hard_failures:
                raise ValueError(
                    "action_execution requires unauthorized_external_write hard failure"
                )
            if not any(grader.get("type") == "trace" for grader in graders):
                raise ValueError("action_execution requires a trace grader")

        return cls(
            schema_version="2.0",
            task_id=task_id,
            name=str(payload["name"]),
            business_scenario=scenario,
            task_type=task_type,
            capability_tags=capability_tags,
            complexity_tags=complexity_tags,
            user_profile=_dict(payload["user_profile"], "user_profile"),
            initial_state=_dict(payload["initial_state"], "initial_state"),
            environment=_dict(payload["environment"], "environment"),
            turns=turns,
            expected_outcome=expected_outcome,
            graders=graders,
            metadata=_dict(payload["metadata"], "metadata"),
        )


def load_task_cases(path: Path) -> list[TaskCase]:
    cases: list[TaskCase] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
            if not isinstance(payload, dict):
                raise ValueError("case must be a JSON object")
            cases.append(TaskCase.from_dict(payload))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid task at {path}:{line_number}: {exc}") from exc

    duplicate_ids = sorted(
        task_id for task_id, count in Counter(case.task_id for case in cases).items() if count > 1
    )
    if duplicate_ids:
        raise ValueError(f"task_id must be unique: {', '.join(duplicate_ids)}")
    return cases


def validate_seed_dataset(cases: Sequence[TaskCase]) -> None:
    if len(cases) != 20:
        raise ValueError(f"expected 20 tasks, found {len(cases)}")

    scenario_counts = Counter(case.business_scenario for case in cases)
    if scenario_counts != Counter(SEED_SCENARIO_QUOTA):
        raise ValueError(
            "scenario quota mismatch: "
            f"expected {SEED_SCENARIO_QUOTA}, found {dict(scenario_counts)}"
        )

    type_counts = Counter(case.task_type for case in cases)
    if type_counts != Counter(SEED_TASK_TYPE_QUOTA):
        raise ValueError(
            f"task type quota mismatch: expected {SEED_TASK_TYPE_QUOTA}, found {dict(type_counts)}"
        )


def _dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return dict(value)


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty array")
    items = tuple(str(item).strip() for item in value)
    if any(not item for item in items):
        raise ValueError(f"{field_name} must not contain empty values")
    return items


def _mapping_tuple(value: Any, field_name: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{field_name} items must be objects")
    return tuple(dict(item) for item in value)
