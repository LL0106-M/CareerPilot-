import json

from careerpilot.evaluation.system_benchmark import (
    build_report,
    retrieval_metrics,
    run_memory_benchmark,
    run_rag_benchmark,
)


def test_retrieval_metrics_measure_recall_precision_and_rank() -> None:
    metrics = retrieval_metrics(["noise", "wanted", "wanted"], ["wanted", "missing"])

    assert metrics == {
        "recall_at_k": 0.5,
        "precision_at_k": 0.5,
        "mrr": 0.5,
    }


def test_no_answer_metrics_reward_an_empty_result() -> None:
    assert retrieval_metrics([], []) == {
        "recall_at_k": 1.0,
        "precision_at_k": 1.0,
        "mrr": 1.0,
    }
    assert retrieval_metrics(["unexpected"], []) == {
        "recall_at_k": 0.0,
        "precision_at_k": 0.0,
        "mrr": 0.0,
    }


def test_rag_benchmark_detects_expected_document_and_owner_leakage(tmp_path) -> None:
    dataset = {
        "schema_version": "1.0",
        "cases": [
            {
                "id": "R-T01",
                "category": "owner_isolation",
                "query": "我的火星计划是什么",
                "user_id": "u-a",
                "limit": 3,
                "documents": [
                    {
                        "id": "own",
                        "title": "A 的计划",
                        "source_uri": "memory://u-a/plan",
                        "source_type": "note",
                        "domain": "career",
                        "text": "我的火星计划是学习机器人产品设计。",
                        "knowledge_origin": "user_provided",
                        "owner_user_id": "u-a",
                    },
                    {
                        "id": "other",
                        "title": "B 的计划",
                        "source_uri": "memory://u-b/plan",
                        "source_type": "note",
                        "domain": "career",
                        "text": "我的火星计划是学习机器人产品设计。",
                        "knowledge_origin": "user_provided",
                        "owner_user_id": "u-b",
                    },
                ],
                "expected_document_ids": ["own"],
                "forbidden_document_ids": ["other"],
            }
        ],
    }
    path = tmp_path / "rag.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    result = run_rag_benchmark(path, tmp_path / "rag-work")

    assert result[0]["passed"] is True
    assert result[0]["retrieved_ids"][0] == "own"
    assert result[0]["hard_failures"] == []


def test_memory_benchmark_enforces_sensitive_recall_boundary(tmp_path) -> None:
    dataset = {
        "schema_version": "1.0",
        "cases": [
            {
                "id": "M-T01",
                "category": "sensitive_default_hidden",
                "kind": "retrieval",
                "owner_id": "u-a",
                "query": "我的心理疾病诊断是什么",
                "purpose": "companion",
                "explicit_personal_recall": False,
                "seed_memories": [
                    {
                        "owner_id": "u-a",
                        "type": "fact",
                        "content": "我的心理疾病诊断是焦虑症",
                        "sensitivity": "sensitive",
                        "confirm": True,
                    }
                ],
                "expected_contents": [],
                "forbidden_contents": ["我的心理疾病诊断是焦虑症"],
            }
        ],
    }
    path = tmp_path / "memory.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    result = run_memory_benchmark(path, tmp_path / "memory-work")

    assert result[0]["passed"] is True
    assert result[0]["retrieved_contents"] == []
    assert result[0]["hard_failures"] == []


def test_report_keeps_rag_and_memory_scores_separate() -> None:
    rag = [
        {
            "id": "R01",
            "category": "direct_fact",
            "passed": True,
            "latency_ms": 10.0,
            "metrics": {"recall_at_k": 1.0, "precision_at_k": 0.5, "mrr": 1.0},
            "failures": [],
            "hard_failures": [],
        }
    ]
    memory = [
        {
            "id": "M01",
            "category": "write_policy",
            "passed": False,
            "latency_ms": 20.0,
            "metrics": {"accuracy": 0.0},
            "failures": ["wrong type"],
            "hard_failures": [],
        }
    ]

    report = build_report(rag, memory, rag_dataset="rag.json", memory_dataset="memory.json")

    assert report["suites"]["rag"]["metrics"]["pass_rate"] == 1.0
    assert report["suites"]["memory"]["metrics"]["pass_rate"] == 0.0
    assert "overall_score" not in report
    assert report["hard_failure_count"] == 0
