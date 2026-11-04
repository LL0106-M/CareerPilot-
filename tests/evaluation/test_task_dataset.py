from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from careerpilot.evaluation.task_dataset import load_task_cases, validate_seed_dataset

SCENARIOS = (
    "emotional_clarification",
    "career_exploration",
    "external_research",
    "action_execution",
    "long_term_review",
)


def _case_payload(
    task_id: str = "EC-01",
    *,
    scenario: str = "emotional_clarification",
    task_type: str = "single_turn",
) -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "task_id": task_id,
        "name": "测试任务",
        "business_scenario": scenario,
        "task_type": task_type,
        "capability_tags": ["intent_decision"],
        "complexity_tags": ["single_session"],
        "user_profile": {"profile_id": "fictional-user-01", "facts": []},
        "initial_state": {
            "memories": [],
            "hypotheses": [],
            "actions": [],
            "conversation": {},
        },
        "environment": {
            "current_time": "2026-11-04T10:00:00+08:00",
            "knowledge_items": [],
            "tools": [],
        },
        "turns": [
            {
                "turn_id": "t1",
                "session_id": "s1",
                "user_message": "我想先说说。",
                "checkpoint": {"support_mode": "listen"},
            }
        ],
        "expected_outcome": {
            "response": {"support_mode": "listen"},
            "trace": {"forbidden_tools": ["action.write"]},
            "state": {"memory_writes": 0},
            "hard_failures": ["unauthorized_external_write"],
        },
        "graders": [
            {"type": "rule", "checks": ["response.support_mode == listen"]}
        ],
        "metadata": {
            "source": "expert_designed",
            "difficulty": "medium",
            "dataset_version": "2.0.0",
            "control_group": "mode-boundary",
            "variable_under_test": "user_goal",
        },
    }


def _write_jsonl(path: Path, payloads: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(payload, ensure_ascii=False) for payload in payloads) + "\n",
        encoding="utf-8",
    )


def test_load_task_cases_parses_valid_jsonl(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    _write_jsonl(dataset, [_case_payload()])

    cases = load_task_cases(dataset)

    assert len(cases) == 1
    assert cases[0].task_id == "EC-01"
    assert cases[0].business_scenario == "emotional_clarification"
    assert cases[0].turns[0]["user_message"] == "我想先说说。"


def test_load_task_cases_reports_file_and_line_for_malformed_json(tmp_path: Path) -> None:
    dataset = tmp_path / "broken.jsonl"
    dataset.write_text("{}\n{broken}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"broken\.jsonl:1"):
        load_task_cases(dataset)


def test_load_task_cases_rejects_duplicate_task_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "duplicates.jsonl"
    _write_jsonl(dataset, [_case_payload(), _case_payload()])

    with pytest.raises(ValueError, match="task_id must be unique: EC-01"):
        load_task_cases(dataset)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("graders", [], "at least one deterministic grader"),
        (
            "expected_outcome",
            {"response": {}, "trace": {}, "state": {}, "hard_failures": []},
            "at least one hard failure",
        ),
    ],
)
def test_load_task_cases_requires_auditable_grading(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    payload = _case_payload()
    payload[field] = value
    dataset = tmp_path / "invalid.jsonl"
    _write_jsonl(dataset, [payload])

    with pytest.raises(ValueError, match=message):
        load_task_cases(dataset)


def test_action_execution_case_requires_authorization_check(tmp_path: Path) -> None:
    payload = _case_payload(scenario="action_execution")
    payload["capability_tags"] = ["tool_execution"]
    dataset = tmp_path / "action.jsonl"
    _write_jsonl(dataset, [payload])

    with pytest.raises(ValueError, match="authorization_control capability"):
        load_task_cases(dataset)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_hard_failure", "unauthorized_external_write hard failure"),
        ("missing_trace_grader", "trace grader"),
    ],
)
def test_action_execution_case_makes_authorization_auditable(
    tmp_path: Path, mutation: str, message: str
) -> None:
    payload = _case_payload(scenario="action_execution")
    payload["capability_tags"] = ["tool_execution", "authorization_control"]
    if mutation == "missing_hard_failure":
        payload["expected_outcome"] = {
            "response": {},
            "trace": {},
            "state": {},
            "hard_failures": ["fabricated_tool_success"],
        }
        payload["graders"] = [{"type": "trace", "checks": ["write not_called"]}]
    else:
        payload["graders"] = [{"type": "rule", "checks": ["reply is non_empty"]}]
    dataset = tmp_path / "action-audit.jsonl"
    _write_jsonl(dataset, [payload])

    with pytest.raises(ValueError, match=message):
        load_task_cases(dataset)


def test_validate_seed_dataset_enforces_scenario_and_task_type_quotas() -> None:
    payloads: list[dict[str, object]] = []
    task_types = ["single_turn"] * 8 + ["multi_turn"] * 7 + ["long_horizon"] * 5
    for index, task_type in enumerate(task_types):
        scenario = SCENARIOS[index // 4]
        payload = _case_payload(
            task_id=f"T-{index + 1:02d}", scenario=scenario, task_type=task_type
        )
        if scenario == "action_execution":
            payload["capability_tags"] = ["tool_execution", "authorization_control"]
            payload["graders"] = [
                {"type": "trace", "checks": ["unauthorized write not_called"]}
            ]
        payloads.append(payload)

    from careerpilot.evaluation.task_dataset import TaskCase

    cases = [TaskCase.from_dict(payload) for payload in payloads]
    validate_seed_dataset(cases)

    with pytest.raises(ValueError, match="expected 20 tasks"):
        validate_seed_dataset(cases[:-1])

    wrong_quota = list(cases)
    wrong_quota[0] = TaskCase.from_dict(
        _case_payload(task_id="T-01", scenario=SCENARIOS[0], task_type="multi_turn")
    )
    with pytest.raises(ValueError, match="task type quota"):
        validate_seed_dataset(wrong_quota)


def test_repository_v2_seed_dataset_has_expected_coverage() -> None:
    dataset = Path("evals/agent/careerpilot-agent-v2.jsonl")
    cases = load_task_cases(dataset)
    validate_seed_dataset(cases)

    assert len(cases) == 20
    assert Counter(case.business_scenario for case in cases) == Counter(
        {scenario: 4 for scenario in SCENARIOS}
    )
    assert Counter(case.task_type for case in cases) == Counter(
        {"single_turn": 8, "multi_turn": 7, "long_horizon": 5}
    )
    assert all(case.metadata["control_group"] for case in cases)
    assert all(case.metadata["variable_under_test"] for case in cases)
