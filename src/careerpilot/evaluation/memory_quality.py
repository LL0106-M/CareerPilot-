from __future__ import annotations

from collections.abc import Iterable, Mapping


def evaluate_memory_quality(
    cases: Iterable[Mapping[str, object]],
) -> dict[str, int | float | bool]:
    rows = list(cases)
    emitted = [row for row in rows if bool(row.get("callback_emitted"))]
    relevant_emitted = sum(bool(row.get("callback_expected")) for row in emitted)
    claims = sum(int(row.get("claims", 0)) for row in rows)
    false_facts = sum(int(row.get("false_facts", 0)) for row in rows)
    correction_cases = [row for row in rows if bool(row.get("correction_expected"))]
    corrections_applied = sum(
        bool(row.get("correction_applied")) for row in correction_cases
    )
    callback_precision = relevant_emitted / len(emitted) if emitted else 1.0
    false_fact_rate = false_facts / claims if claims else 0.0
    correction_rate = (
        corrections_applied / len(correction_cases) if correction_cases else 1.0
    )
    return {
        "case_count": len(rows),
        "callback_precision": callback_precision,
        "false_fact_rate": false_fact_rate,
        "correction_handling_rate": correction_rate,
        "passed": (
            callback_precision >= 0.8
            and false_fact_rate <= 0.05
            and correction_rate >= 0.9
        ),
    }

