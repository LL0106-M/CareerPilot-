# CareerPilot 技术架构

这份文档是 CareerPilot 当前技术设计的主入口。它解释整体边界和关键数据流；具体协议、数据模型与历史取舍放在下方专题文档中。

## 1. 架构目标

CareerPilot 采用“单前台 Agent + 自有 Harness”，。

模型负责语义判断：理解用户、选择支持方式、提出工具调用和组织回答。确定性代码负责不可让模型自行突破的边界：用户隔离、会话状态、最大步数、记忆准入、检索范围、工具白名单和外部动作确认。

```text
┌─────────────────────────────────────────────────────────────┐
│ React / Vite                                                │
│ 今日 · 对话 · Dreaming · 罗盘 · 航程 · 知识库               │
└──────────────────────────┬──────────────────────────────────┘
                           │ authenticated HTTP / stream
┌──────────────────────────▼──────────────────────────────────┐
│ FastAPI / AgentService                                     │
│                                                            │
│ Intent → RetrievalPlan → Context Compiler → Runtime         │
│                              │          │                  │
│                 Memory/RAG ──┘          ├─ internal tools  │
│                                         ├─ MCP tools       │
│                                         └─ Action Service  │
└───────────────┬────────────────┬─────────────────┬─────────┘
                │                │                 │
        Session & Events   Memory & Domain   Knowledge Index
```

## 2. 一轮对话的数据流

```text
用户消息
→ IntentInterpreter 识别支持模式、任务意图和当前条件
→ RetrievalRouter 生成受约束的 RetrievalPlan
→ ContextCompiler 按计划读取记忆、认知状态与知识证据
→ Runtime 调用模型
→ ToolPolicy 校验并执行允许的工具调用
→ 模型基于工具结果继续或完成回复
→ 保存会话与运行事件
→ MemoryLifecycle 在回复后执行写入准入并按需排队 Dreaming
```

`RetrievalPlan` 是关键隔离层：模型不能因为 Prompt 中的一句话自行扩大数据源、读取其他用户内容或暴露整个工具目录。当前上下文已经足够时，Memory 和 RAG 都可以跳过。

## 3. Memory + RAG：同一套上下文系统

Memory 和 RAG 都为 Agent 提供上下文，但它们回答不同问题，必须在同一检索计划下协作，而不能混成一个向量库。

| 上下文层 | 回答的问题 | 真相来源 | 典型内容 |
|---|---|---|---|
| Working Context | 用户这轮在说什么？ | 当前会话 | 当前消息、最近轮次、工具结果 |
| Personal Memory | 关于这个用户，什么值得跨会话复用？ | 用户事件 + 写入策略 | 偏好、目标、约束、经历 |
| Cognitive State | 我们正在验证什么职业判断？ | 结构化领域状态 | 方向、假设、证据、反证、信心 |
| Product State | 产品已经承诺或执行了什么？ | 确定性业务状态 | 任务、日历、权限、回执 |
| Governed RAG | 外部世界有哪些可回源依据？ | 私有文档与职业知识索引 | 岗位、面试经验、学习资源、网页 |

### 写入路径

```text
Conversation / Action Event
→ Extract candidate
→ MemoryWritePolicy
→ Store + Index
→ optional Dreaming consolidation
→ reviewable patch / hypothesis
```

模型只提出候选。写入策略检查来源、所有者、稳定性、敏感度、冲突和版本；Dreaming 只能基于快照内证据生成可审查提案。方向、航程、任务和日历属于领域状态，不是“记忆”。

### 读取路径

```text
Current Intent
→ choose allowed sources and budgets
→ retrieve per source
→ filter owner / sensitivity / freshness
→ rerank and deduplicate
→ compile attributed context
```

个人记忆与公共知识分别检索、分别限额。用户当前原话和已确认的本地状态优先于历史候选；强时效事实必须带来源和日期，资料不足时返回 `partial` 或诚实停止。

## 4. Runtime：限制 Agent 如何运行

`CareerPilotHarness.stream()` 是统一执行入口。它发出与模型供应商无关的运行事件，非流式调用只是消费同一事件流。

```text
run.started
→ model.started → model.text_delta* → model.completed
→ [tool.requested → tool.started → tool.completed → model.started]*
→ run.completed | run.failed | run.cancelled
```

Runtime 负责：

- 持久化 Session 和模型/工具消息；
- 约束合法状态迁移、最大步数、取消与失败语义；
- 记录 `run_id`、`session_id`、序号、阶段和用量；
- 在模型网关、工具系统和 API 之间保持稳定协议；
- 让工具失败可以降级，而不是让整个对话失去边界。

模型适配器可以替换，供应商事件不会泄漏到产品层。

## 5. MCP 与外部动作：扩展能力但不扩张权限

MCP 是可插拔工具来源，不是 Agent Runtime。CareerPilot 作为 MCP Host 发现工具，将少量相关工具适配进当前轮的统一注册表。

```text
configured server
→ discover descriptors
→ cache and select relevant tools
→ enforce read-only / non-destructive policy
→ expose bounded schemas to the model
→ recheck policy before call
→ bound and mark untrusted result
```

首版 MCP 只暴露明确标注为只读、非破坏性的工具。未标注风险、写入型、破坏性或指纹过期的工具默认拒绝；发现失败不会影响内部对话和 RAG。

需要写入日历、邮箱或协作平台的动作走独立 Action Service：

```text
preview → user confirm → apply → verify
```

这让“模型认为应该做”与“系统被授权执行”保持分离。

## 6. 代码地图

```text
frontend/                   React 产品前台
src/careerpilot/
├── agent/                  Agent 定义、Prompt 与 Turn 编排
├── context/                意图识别、检索计划与上下文编译
├── harness/                Runtime、Session、事件与工具策略
├── memory/                 长期记忆、认知状态与 Dreaming
├── rag/                    知识索引、混合召回与证据规范化
├── mcp/                    MCP 配置、发现、选择和安全策略
├── actions/                预览、确认、执行与验证
├── connectors/             飞书、WPS、网易邮箱等适配器
├── journey/                方向到行动的领域流程
├── evaluation/             Agent、Memory 与 RAG 评测运行器
└── api/                    FastAPI 路由与 Schema
```

## 7. 当前主文档

| 主题 | 文档 | 用途 |
|---|---|---|
| 整体 Harness | [CareerPilot Harness Architecture](careerpilot-harness.md) | Runtime、上下文计划、事件协议和故障边界 |
| 情绪识别与回应控制 | [Emotion Recognition](emotion-recognition.md) | 当前规则、支持模式、回答契约、安全覆盖和记忆边界 |
| Memory | [Agent Memory Handbook](agent-memory-handbook.md) | 记忆类型、写入、召回、冲突、Dreaming 与上线条件 |
| 产品与权限 | [CareerPilot MVP PRD](../../PRD/CareerPilot-MVP-PRD-v1.0.md) | 产品目标、支持模式、自治等级与上线门槛 |
| Memory/RAG 详细设计 | [Memory + RAG Technical Design](../../PRD/CareerPilot-Memory-RAG-Technical-Design.md) | 完整数据模型、接口、检索与安全设计 |
| 意图与路由 | [Intent and Task Decomposition](../../PRD/CareerPilot-Intent-and-Task-Decomposition-PRD-v0.1.md) | 意图、槽位、能力路由和产品契约 |
| MCP 专题 | [MCP Tool Platform Design](../superpowers/specs/2026-11-03-mcp-tool-platform-design.md) | MCP 发现、选择、策略、缓存与错误处理 |

`docs/superpowers/plans/` 与 `docs/superpowers/specs/` 记录每次实现的计划和设计历史。它们用于追溯决策，不作为当前架构的首要入口；若历史文档与本页或主手册冲突，以当前代码、测试和上述主文档为准。

## 8. 评测与运行

- [评测中心：最新基线、数据集与复现](../evaluation/README.md)
- [本地开发、部署与 MCP 配置](../development.md)
- [完整文档地图](../README.md)
