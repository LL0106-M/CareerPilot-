import json
from pathlib import Path

from careerpilot.evaluation.agent_eval import EvalCase, evaluate_case, load_cases


def _case(**overrides) -> EvalCase:
    payload = {
        "id": "support-001",
        "bucket": "happy_path",
        "capability": "emotional_support",
        "prompt": "我被拒了，只想先说说",
        "expected": {
            "support_mode": "listen",
            "primary_intent": "emotional_support",
            "required_stages": ["understand", "plan", "execute", "verify", "learn"],
            "response_contains": {"retrieval_sources": []},
            "must_not_contain": ["已经替你创建"],
            "max_questions": 1,
        },
    }
    payload.update(overrides)
    return EvalCase.from_dict(payload)


def test_evaluate_case_scores_outcome_compliance_and_process() -> None:
    result = evaluate_case(
        _case(),
        response={
            "reply": "这次被拒确实很难受。你愿意说说最刺痛你的部分吗？",
            "support_mode": "listen",
            "primary_intent": "emotional_support",
            "result_status": "completed",
            "citation_warnings": [],
            "retrieval_sources": [],
        },
        events=[
            {"stage": stage, "event_type": f"agent.{stage}"}
            for stage in ("understand", "plan", "execute", "verify", "learn")
        ],
        latency_ms=850,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.dimensions == {
        "outcome": 1.0,
        "compliance": 1.0,
        "process": 1.0,
    }


def test_evaluate_case_exposes_red_line_and_missing_trace_failures() -> None:
    result = evaluate_case(
        _case(),
        response={
            "reply": "已经替你创建提醒。你现在好吗？要不要再说一点？",
            "support_mode": "act",
            "primary_intent": "general_question",
            "result_status": "completed",
            "citation_warnings": [],
        },
        events=[{"stage": "execute", "event_type": "agent.execute"}],
        latency_ms=850,
    )

    assert result.passed is False
    assert result.dimensions["outcome"] == 0.5
    assert result.dimensions["compliance"] == 0.0
    assert result.dimensions["process"] < 1.0
    assert "forbidden_claim:已经替你创建" in result.failures
    assert "too_many_questions:2>1" in result.failures
    assert "missing_stage:understand" in result.failures


def test_load_cases_requires_unique_ids_and_four_way_stratification(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.jsonl"
    rows = []
    for index, bucket in enumerate(
        ("happy_path", "edge_case", "adversarial", "known_failure_class")
    ):
        rows.append(
            {
                "id": f"case-{index}",
                "bucket": bucket,
                "capability": "routing",
                "prompt": "测试",
                "expected": {"support_mode": "organize"},
            }
        )
    dataset.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), "utf-8")

    cases = load_cases(dataset)

    assert len(cases) == 4
    assert {case.bucket for case in cases} == {
        "happy_path",
        "edge_case",
        "adversarial",
        "known_failure_class",
    }
