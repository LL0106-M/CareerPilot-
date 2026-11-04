from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from careerpilot.memory.models import MemorySensitivity, MemoryStatus, MemoryType
from careerpilot.memory.service import MemoryQueryPurpose, MemoryService
from careerpilot.memory.unified_store import SqliteUnifiedMemoryStore
from careerpilot.memory.write_policy import MemoryWritePolicy
from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.models import KnowledgeOrigin, SourceDocument
from careerpilot.rag.query_analysis import GraphSearchMode
from careerpilot.rag.retrieval import RagRetriever
from careerpilot.rag.store import SqliteRagStore


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def retrieval_metrics(retrieved: list[str], expected: list[str]) -> dict[str, float]:
    retrieved = _unique(retrieved)
    expected_set = set(expected)
    if not expected_set:
        score = 1.0 if not retrieved else 0.0
        return {"recall_at_k": score, "precision_at_k": score, "mrr": score}
    relevant = [item for item in retrieved if item in expected_set]
    first_rank = next(
        (index for index, item in enumerate(retrieved, start=1) if item in expected_set),
        None,
    )
    return {
        "recall_at_k": round(len(set(relevant)) / len(expected_set), 4),
        "precision_at_k": round(len(relevant) / len(retrieved), 4) if retrieved else 0.0,
        "mrr": round(1.0 / first_rank, 4) if first_rank else 0.0,
    }


def _read_dataset(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _document(raw: dict[str, Any]) -> SourceDocument:
    return SourceDocument(
        id=raw["id"],
        title=raw["title"],
        source_uri=raw["source_uri"],
        source_type=raw["source_type"],
        domain=raw["domain"],
        text=raw["text"],
        metadata=raw.get("metadata", {}),
        published_at=raw.get("published_at"),
        fetched_at=raw.get("fetched_at"),
        knowledge_origin=KnowledgeOrigin(raw.get("knowledge_origin", "system_curated")),
        owner_user_id=raw.get("owner_user_id"),
    )


def run_rag_benchmark(dataset_path: str | Path, work_dir: str | Path) -> list[dict[str, Any]]:
    dataset = _read_dataset(dataset_path)
    workspace = Path(work_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for case in dataset["cases"]:
        started = time.perf_counter()
        failures: list[str] = []
        hard_failures: list[str] = []
        store = SqliteRagStore(workspace / f"{case['id']}.db")
        try:
            for raw in case["documents"]:
                document = _document(raw)
                store.upsert(document, chunk_document(document))
            result = RagRetriever(store).retrieve(
                case["query"],
                domain=case.get("domain"),
                sub_queries=tuple(case.get("sub_queries", [])),
                requires_freshness=case.get("requires_freshness", False),
                validation_target=case.get("validation_target", "direct_fact"),
                user_id=case.get("user_id"),
                origins=(
                    frozenset(KnowledgeOrigin(item) for item in case["origins"])
                    if case.get("origins")
                    else None
                ),
                use_graph=case.get("use_graph"),
                graph_mode=GraphSearchMode(case.get("graph_mode", "none")),
                limit=case.get("limit", 5),
            )
            retrieved = _unique([hit.document_id for hit in result.hits])
            expected = case.get("expected_document_ids", [])
            forbidden = set(case.get("forbidden_document_ids", []))
            metrics = retrieval_metrics(retrieved, expected)
            missing = set(expected) - set(retrieved)
            forbidden_hits = forbidden & set(retrieved)
            leaks = {
                hit.document_id
                for hit in result.hits
                if hit.owner_user_id is not None and hit.owner_user_id != case.get("user_id")
            }
            if missing:
                failures.append(f"未召回期望文档：{', '.join(sorted(missing))}")
            if not expected and retrieved:
                failures.append(f"无答案场景出现意外召回：{', '.join(retrieved)}")
            if forbidden_hits:
                message = f"召回禁止文档：{', '.join(sorted(forbidden_hits))}"
                failures.append(message)
                if case.get("forbidden_is_hard", True):
                    hard_failures.append(message)
            if leaks:
                message = f"跨用户文档泄漏：{', '.join(sorted(leaks))}"
                failures.append(message)
                hard_failures.append(message)
            results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "passed": not failures,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "metrics": metrics,
                    "retrieved_ids": retrieved,
                    "expected_ids": expected,
                    "status": result.status,
                    "failures": failures,
                    "hard_failures": hard_failures,
                }
            )
        except Exception as exc:  # benchmark must report case-level failures
            message = f"运行异常：{type(exc).__name__}: {exc}"
            results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "passed": False,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "metrics": {"recall_at_k": 0.0, "precision_at_k": 0.0, "mrr": 0.0},
                    "retrieved_ids": [],
                    "expected_ids": case.get("expected_document_ids", []),
                    "status": "error",
                    "failures": [message],
                    "hard_failures": [message],
                }
            )
        finally:
            store.close()
    return results


def _seed_memory(service: MemoryService, raw: dict[str, Any]) -> None:
    record = service.create_explicit(
        owner_id=raw["owner_id"],
        memory_type=MemoryType(raw["type"]),
        content=raw["content"],
        sensitivity=MemorySensitivity(raw.get("sensitivity", "normal")),
        importance=raw.get("importance", 3),
        source_reference=raw.get("source_reference", "benchmark-seed"),
    )
    if raw.get("confirm") and record.status is MemoryStatus.CANDIDATE:
        service.confirm(record.owner_id, record.id, expected_version=record.version)


def _run_memory_case(service: MemoryService, case: dict[str, Any]) -> dict[str, Any]:
    kind = case["kind"]
    failures: list[str] = []
    hard_failures: list[str] = []
    metrics: dict[str, float]
    retrieved: list[str] = []
    if kind == "retrieval":
        for item in case.get("seed_memories", []):
            _seed_memory(service, item)
        bundle = service.search_context(
            owner_id=case["owner_id"],
            query=case["query"],
            purpose=MemoryQueryPurpose(case.get("purpose", "companion")),
            limit=case.get("limit", 8),
            explicit_personal_recall=case.get("explicit_personal_recall", False),
            broad_recall=case.get("broad_recall", False),
        )
        retrieved = _unique([record.content for record in bundle.records])
        expected = case.get("expected_contents", [])
        forbidden = set(case.get("forbidden_contents", []))
        metrics = retrieval_metrics(retrieved, expected)
        missing = set(expected) - set(retrieved)
        forbidden_hits = forbidden & set(retrieved)
        if missing:
            failures.append(f"未召回期望记忆：{', '.join(sorted(missing))}")
        if not expected and retrieved:
            failures.append(f"无答案场景出现意外召回：{', '.join(retrieved)}")
        if forbidden_hits:
            message = f"暴露禁止记忆：{', '.join(sorted(forbidden_hits))}"
            failures.append(message)
            hard_failures.append(message)
    elif kind == "write_policy":
        candidates = MemoryWritePolicy().extract(case["message"])
        actual_types = [candidate.type.value for candidate in candidates]
        expected_types = case.get("expected_types", [])
        passed = len(candidates) == case["expected_count"] and actual_types == expected_types
        metrics = {"accuracy": 1.0 if passed else 0.0}
        if not passed:
            failures.append(
                f"写入策略不符：期望 {expected_types}，实际 {actual_types}"
            )
        if case.get("hard_if_admitted") and candidates:
            message = "短暂情绪被错误写入长期记忆"
            hard_failures.append(message)
            failures.append(message)
    elif kind == "correction":
        old = case["old_memory"]
        _seed_memory(service, old)
        old_record = service.list(case["owner_id"])[0]
        new = case["new_memory"]
        service.remember_from_conversation(
            owner_id=case["owner_id"],
            memory_type=MemoryType(new["type"]),
            content=new["content"],
            sensitivity=MemorySensitivity(new.get("sensitivity", "normal")),
            importance=new.get("importance", 4),
            source_reference="benchmark-correction",
            correction=True,
        )
        old_status = service.get(case["owner_id"], old_record.id).status
        passed = old_status is MemoryStatus.SUPERSEDED
        metrics = {"lifecycle_accuracy": 1.0 if passed else 0.0}
        if not passed:
            message = "更正后旧记忆未被标记为 superseded"
            failures.append(message)
            hard_failures.append(message)
    elif kind == "deduplication":
        memory = case["memory"]
        _seed_memory(service, memory)
        _seed_memory(service, memory)
        records = service.list(case["owner_id"])
        passed = len(records) == case.get("expected_count", 1)
        metrics = {"lifecycle_accuracy": 1.0 if passed else 0.0}
        if not passed:
            failures.append(f"重复写入后存在 {len(records)} 条记录")
    else:
        raise ValueError(f"unsupported memory benchmark kind: {kind}")
    return {
        "metrics": metrics,
        "retrieved_contents": retrieved,
        "failures": failures,
        "hard_failures": hard_failures,
    }


def run_memory_benchmark(
    dataset_path: str | Path, work_dir: str | Path
) -> list[dict[str, Any]]:
    dataset = _read_dataset(dataset_path)
    workspace = Path(work_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for case in dataset["cases"]:
        started = time.perf_counter()
        store = SqliteUnifiedMemoryStore(workspace / f"{case['id']}.db")
        try:
            detail = _run_memory_case(MemoryService(store), case)
            results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "passed": not detail["failures"],
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    **detail,
                }
            )
        except Exception as exc:  # benchmark must report case-level failures
            message = f"运行异常：{type(exc).__name__}: {exc}"
            results.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "passed": False,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "metrics": {"accuracy": 0.0},
                    "retrieved_contents": [],
                    "failures": [message],
                    "hard_failures": [message],
                }
            )
        finally:
            store.close()
    return results


def _suite(results: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = sorted({name for item in results for name in item["metrics"]})
    metrics: dict[str, float | int] = {
        "case_count": len(results),
        "passed_count": sum(item["passed"] for item in results),
        "pass_rate": round(sum(item["passed"] for item in results) / len(results), 4)
        if results
        else 0.0,
        "p50_latency_ms": round(statistics.median(item["latency_ms"] for item in results), 2)
        if results
        else 0.0,
        "hard_failure_count": sum(len(item["hard_failures"]) for item in results),
    }
    for name in metric_names:
        values = [item["metrics"][name] for item in results if name in item["metrics"]]
        metrics[name] = round(sum(values) / len(values), 4)
    return {"metrics": metrics, "results": results}


def build_report(
    rag_results: list[dict[str, Any]],
    memory_results: list[dict[str, Any]],
    *,
    rag_dataset: str,
    memory_dataset: str,
) -> dict[str, Any]:
    hard_failures = [
        {"suite": suite_name, "case_id": item["id"], "message": message}
        for suite_name, results in (("rag", rag_results), ("memory", memory_results))
        for item in results
        for message in item["hard_failures"]
    ]
    return {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone(timedelta(hours=8), "Asia/Shanghai")).isoformat(),
        "datasets": {"rag": rag_dataset, "memory": memory_dataset},
        "suites": {"rag": _suite(rag_results), "memory": _suite(memory_results)},
        "hard_failure_count": len(hard_failures),
        "hard_failures": hard_failures,
        "limitations": [
            "本轮为冻结语料上的离线确定性基线，不调用外部模型或网络。",
            "RAG 仅评测召回层，不评测最终答案忠实度与引用生成质量。",
            "记忆评测覆盖召回、写入门控和生命周期，不代表真实用户分布。",
        ],
    }


def _metric(value: Any) -> str:
    return f"{value * 100:.1f}%" if isinstance(value, float) and 0 <= value <= 1 else str(value)


def render_markdown(report: dict[str, Any]) -> str:
    rag = report["suites"]["rag"]["metrics"]
    memory = report["suites"]["memory"]["metrics"]
    rag_summary = (
        f"- RAG：{rag['passed_count']}/{rag['case_count']} 通过，"
        f"Pass Rate {_metric(rag['pass_rate'])}。"
    )
    memory_summary = (
        f"- 记忆：{memory['passed_count']}/{memory['case_count']} 通过，"
        f"Pass Rate {_metric(memory['pass_rate'])}。"
    )
    rag_row = (
        f"| RAG | {_metric(rag['pass_rate'])} | {_metric(rag.get('recall_at_k', 0))} | "
        f"{_metric(rag.get('precision_at_k', 0))} | {_metric(rag.get('mrr', 0))} | "
        f"{rag['p50_latency_ms']} ms | {rag['hard_failure_count']} |"
    )
    memory_row = (
        f"| 记忆 | {_metric(memory['pass_rate'])} | "
        f"{_metric(memory.get('recall_at_k', 0))} | "
        f"{_metric(memory.get('precision_at_k', 0))} | "
        f"{_metric(memory.get('mrr', 0))} | {memory['p50_latency_ms']} ms | "
        f"{memory['hard_failure_count']} |"
    )
    lines = [
        "# CareerPilot RAG 与记忆系统评测报告",
        "",
        f"生成时间：{report['created_at']}",
        "",
        "## 结论摘要",
        "",
        rag_summary,
        memory_summary,
        f"- 硬失败：{report['hard_failure_count']} 项。硬失败独立报告，不与普通质量分合并。",
        "",
        "## 分系统指标",
        "",
        "| 系统 | Pass Rate | Recall@K | Precision@K | MRR | P50 延迟 | 硬失败 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        rag_row,
        memory_row,
        "",
    ]
    for suite_name, title in (("rag", "RAG 明细"), ("memory", "记忆系统明细")):
        lines.extend(
            [
                f"## {title}",
                "",
                "| Case | 类别 | 结果 | 延迟 | 失败原因 |",
                "|---|---|---:|---:|---|",
            ]
        )
        for item in report["suites"][suite_name]["results"]:
            reason = "；".join(item["failures"]) or "—"
            outcome = "通过" if item["passed"] else "失败"
            lines.append(
                f"| {item['id']} | {item['category']} | {outcome} | "
                f"{item['latency_ms']} ms | {reason} |"
            )
        lines.append("")
    lines.extend(["## 硬失败", ""])
    if report["hard_failures"]:
        for item in report["hard_failures"]:
            lines.append(f"- {item['suite']} / {item['case_id']}：{item['message']}")
    else:
        lines.append("本轮未发现跨用户泄漏、敏感信息越权暴露或运行异常。")
    lines.extend(["", "## 适用边界", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(
        [
            "",
            "## 如何复现",
            "",
            "```powershell",
            "python -m careerpilot.evaluation.system_benchmark `",
            "  --rag-dataset evals/rag/careerpilot-rag-seed-v1.json `",
            "  --memory-dataset evals/memory/careerpilot-memory-seed-v1.json `",
            "  --output-json evals/reports/2026-11-05-system-benchmark-v1.json `",
            "  --output-md evals/reports/2026-11-05-system-benchmark-v1.md",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CareerPilot RAG and memory benchmarks")
    parser.add_argument("--rag-dataset", required=True)
    parser.add_argument("--memory-dataset", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--work-dir", default=".benchmark-work")
    args = parser.parse_args()
    work = Path(args.work_dir)
    rag_results = run_rag_benchmark(args.rag_dataset, work / "rag")
    memory_results = run_memory_benchmark(args.memory_dataset, work / "memory")
    report = build_report(
        rag_results,
        memory_results,
        rag_dataset=args.rag_dataset,
        memory_dataset=args.memory_dataset,
    )
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
