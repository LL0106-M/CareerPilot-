# CareerPilot 评测中心

CareerPilot 不只评估“回答读起来是否不错”。评测同时检查 Agent 是否选择了正确的支持模式和数据源、工具调用顺序是否合规、Memory/方向/行动状态是否正确变化，以及是否触发安全硬失败。

## 最新公开基线

报告时间：2026-11-05。数据使用虚构用户、冻结语料和独立 SQLite 数据库，运行生产 Memory/RAG 组件；不调用外部模型或网络。

| 系统 | Pass Rate | Recall@K | Precision@K | MRR | P50 延迟 | 硬失败 |
|---|---:|---:|---:|---:|---:|---:|
| RAG | 87.5%（7/8） | 100.0% | 93.8% | 100.0% | 195.02 ms | 0 |
| Memory | 100.0%（10/10） | 100.0% | 100.0% | 100.0% | 33.45 ms | 0 |

本轮唯一失败项是 RAG 时效性 Case `R08`：当前资料被召回的同时，过期的招聘截止日期也没有被重排或过滤。它说明 `requires_freshness` 已进入查询计划，但时间元数据还没有完整转化为召回规则。

本轮未发现跨用户泄漏、敏感信息越权暴露或运行异常。

- [阅读完整 Markdown 报告](../../evals/reports/2026-11-05-system-benchmark-v1.md)
- [下载机器可读 JSON](../../evals/reports/2026-11-05-system-benchmark-v1.json)

## 三层评测体系

| 层级 | 回答的问题 | 当前资产 |
|---|---|---|
| 单元与集成测试 | 函数、状态机、隔离和接口是否符合契约？ | `tests/` |
| Memory/RAG 基准 | 召回、时效、隐私门控和生命周期是否正确？ | 18 条冻结 Case + 可重复运行器 |
| AgentEval | Agent 在真实业务场景中是否做对决策？ | v1 回归集 + v2 20 条业务场景种子集 |

## AgentEval v2

AgentEval v2 不按 `memory`、`rag`、`tool` 等代码目录分类，而按用户真正经历的五类场景组织：

1. 情绪表达与问题澄清；
2. 职业认知与方向探索；
3. 外部信息调研与验证；
4. 行动规划与执行；
5. 行动反馈与长期复盘。

每条任务分别评价四个表面：

- **Outcome**：模式、意图和回复是否满足用户目标；
- **Trace**：是否调用正确来源和工具，顺序是否合规；
- **State**：Memory、方向假设和行动状态是否正确变化；
- **Quality**：是否具体、忠实、克制，并尊重用户控制。

未经确认执行外部写操作、跨用户读取记忆、虚构工具成功、固化一次性负面表达等问题会直接触发硬失败，不与普通质量分取平均。

[阅读 AgentEval v2 建构方法 →](careerpilot-agenteval-v2-construction.md)

## Memory 与 RAG 冻结基准

### RAG：8 条 Case

覆盖直接事实、领域过滤、多来源、图证据、Parent-Child 上下文、无答案、用户隔离和时效性。主要指标为 Recall@K、Precision@K、MRR、Pass Rate 与 P50 延迟。

### Memory：10 条 Case

覆盖偏好与目标召回、无关抑制、用户隔离、敏感信息门控、短暂情绪拒写、稳定信息写入、更正替代与去重。跨用户泄漏、未授权敏感信息暴露和短暂负面表达被固化均为硬失败。

[阅读冻结基准建构说明 →](careerpilot-system-benchmark-design.md)

## 数据集与运行器

| 资产 | 路径 |
|---|---|
| AgentEval v2 | [`evals/agent/careerpilot-agent-v2.jsonl`](../../evals/agent/careerpilot-agent-v2.jsonl) |
| RAG Seed v1 | [`evals/rag/careerpilot-rag-seed-v1.json`](../../evals/rag/careerpilot-rag-seed-v1.json) |
| Memory Seed v1 | [`evals/memory/careerpilot-memory-seed-v1.json`](../../evals/memory/careerpilot-memory-seed-v1.json) |
| System Benchmark | [`src/careerpilot/evaluation/system_benchmark.py`](../../src/careerpilot/evaluation/system_benchmark.py) |

复现最新系统基线：

```powershell
python -m careerpilot.evaluation.system_benchmark `
  --rag-dataset evals/rag/careerpilot-rag-seed-v1.json `
  --memory-dataset evals/memory/careerpilot-memory-seed-v1.json `
  --output-json evals/reports/system-benchmark.json `
  --output-md evals/reports/system-benchmark.md
```

## 如何解读这些数字

当前结果是 MVP 离线确定性基线，不代表真实用户请求分布，也不覆盖最终答案忠实度、引用生成质量或长期在线稳定性。一个高通过率不能抵消任何隐私或授权硬失败；后续版本应加入匿名化真实 Trace、多次 Trial、故障注入、长程对话和端到端回答评测。
