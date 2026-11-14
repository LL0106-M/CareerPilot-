import json
from pathlib import Path

from careerpilot.evaluation.memory_quality import evaluate_memory_quality


def test_memory_quality_dataset_meets_release_thresholds() -> None:
    dataset = Path(__file__).parents[2] / "evals" / "memory_quality_cases.json"
    cases = json.loads(dataset.read_text("utf-8"))

    report = evaluate_memory_quality(cases)

    assert report["case_count"] >= 8
    assert report["callback_precision"] >= 0.8
    assert report["false_fact_rate"] <= 0.05
    assert report["correction_handling_rate"] >= 0.9
    assert report["passed"] is True


def test_memory_quality_flags_irrelevant_callbacks_false_facts_and_ignored_corrections() -> None:
    report = evaluate_memory_quality(
        [
            {
                "id": "bad",
                "callback_expected": False,
                "callback_emitted": True,
                "claims": 1,
                "false_facts": 1,
                "correction_expected": True,
                "correction_applied": False,
            }
        ]
    )

    assert report["callback_precision"] == 0.0
    assert report["false_fact_rate"] == 1.0
    assert report["correction_handling_rate"] == 0.0
    assert report["passed"] is False

