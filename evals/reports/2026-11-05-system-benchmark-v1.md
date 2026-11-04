# CareerPilot RAG 与记忆系统评测报告

生成时间：2026-11-05T01:03:43.050684+08:00

## 结论摘要

- RAG：7/8 通过，Pass Rate 87.5%。
- 记忆：10/10 通过，Pass Rate 100.0%。
- 硬失败：0 项。硬失败独立报告，不与普通质量分合并。

## 分系统指标

| 系统 | Pass Rate | Recall@K | Precision@K | MRR | P50 延迟 | 硬失败 |
|---|---:|---:|---:|---:|---:|---:|
| RAG | 87.5% | 100.0% | 93.8% | 100.0% | 195.02 ms | 0 |
| 记忆 | 100.0% | 100.0% | 100.0% | 100.0% | 33.45 ms | 0 |

## RAG 明细

| Case | 类别 | 结果 | 延迟 | 失败原因 |
|---|---|---:|---:|---|
| R01 | direct_fact | 通过 | 220.84 ms | — |
| R02 | domain_filter | 通过 | 190.81 ms | — |
| R03 | multi_source | 通过 | 209.37 ms | — |
| R04 | graph_evidence | 通过 | 193.81 ms | — |
| R05 | parent_child_context | 通过 | 187.84 ms | — |
| R06 | no_answer | 通过 | 195.41 ms | — |
| R07 | owner_isolation | 通过 | 210.53 ms | — |
| R08 | freshness | 失败 | 194.63 ms | 召回禁止文档：deadline-old |

## 记忆系统明细

| Case | 类别 | 结果 | 延迟 | 失败原因 |
|---|---|---:|---:|---|
| M01 | preference_recall | 通过 | 45.63 ms | — |
| M02 | goal_recall | 通过 | 36.8 ms | — |
| M03 | irrelevant_suppression | 通过 | 32.34 ms | — |
| M04 | owner_isolation | 通过 | 34.55 ms | — |
| M05 | sensitive_default_hidden | 通过 | 29.44 ms | — |
| M06 | sensitive_explicit_recall | 通过 | 31.28 ms | — |
| M07 | transient_write_rejection | 通过 | 29.4 ms | — |
| M08 | durable_write_admission | 通过 | 31.73 ms | — |
| M09 | correction | 通过 | 42.22 ms | — |
| M10 | deduplication | 通过 | 36.44 ms | — |

## 硬失败

本轮未发现跨用户泄漏、敏感信息越权暴露或运行异常。

## 适用边界

- 本轮为冻结语料上的离线确定性基线，不调用外部模型或网络。
- RAG 仅评测召回层，不评测最终答案忠实度与引用生成质量。
- 记忆评测覆盖召回、写入门控和生命周期，不代表真实用户分布。

## 如何复现

```powershell
python -m careerpilot.evaluation.system_benchmark `
  --rag-dataset evals/rag/careerpilot-rag-seed-v1.json `
  --memory-dataset evals/memory/careerpilot-memory-seed-v1.json `
  --output-json evals/reports/2026-11-05-system-benchmark-v1.json `
  --output-md evals/reports/2026-11-05-system-benchmark-v1.md
```
