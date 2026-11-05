# CareerPilot Agent Harness 架构

本文描述的是 CareerPilot **当前代码实际运行的 Agent 架构**，重点说明
`AgentService`、上下文编译器与 `CareerPilotHarness` 之间的边界。

CareerPilot 采用一个面向用户的 Agent，而不是多 Agent 团队。模型负责语义理解、工具选择和回答生成；
确定性代码负责用户隔离、上下文范围、工具权限、运行状态、记忆准入和外部动作确认。

## 1. 架构定位

`CareerPilotHarness` 不是整个产品后端，也不负责职业方向、记忆或 RAG 的业务决策。它是
**模型—工具循环的执行内核**：接收已经编译好的上下文与本轮工具白名单，然后以可追踪、可取消、
有步数和超时限制的方式完成一次 Agent 运行。

与它配合的三个核心边界是：

| 组件 | 核心职责 |
|---|---|
| `AgentService` | 编排一轮任务：理解、规划、执行、校验、学习 |
| `CareerContextCompiler` | 在运行前决定读取什么，并生成受限上下文与工具白名单 |
| `CareerPilotHarness` | 在运行中控制模型调用、工具执行、会话和事件 |
| `MemoryLifecycle` | 在运行后判断什么信息可以进入长期记忆或 Dreaming 队列 |

## 2. 当前运行架构

```text
认证后的用户消息
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ AgentService：任务编排                                      │
│ UNDERSTAND → PLAN → EXECUTE → VERIFY → LEARN                │
└──────────────┬──────────────────────────────┬───────────────┘
               │ 运行前                       │ 运行后
               ▼                              ▼
┌──────────────────────────────┐   ┌──────────────────────────┐
│ CareerContextCompiler        │   │ AgentVerifier            │
│                              │   │ MemoryLifecycle          │
│ IntentFrame                  │   │ DirectionSignalDetector  │
│ RetrievalPlan               │   │                          │
│ Support / Response Strategy  │   │ 回复校验、记忆准入、      │
│ Memory / Cognitive Context   │   │ Dreaming 与方向信号       │
│ Prompt + Tool Allowlist      │   └──────────────────────────┘
└──────────────┬───────────────┘
               │ 编译后的 System Context
               │ 本轮工具白名单与动态工具
               ▼
┌─────────────────────────────────────────────────────────────┐
│ CareerPilotHarness：执行内核                                │
│                                                             │
│ Session → Context Window → Model ⇄ Tools → Final Response   │
│                                                             │
│ 状态机 · 最大步数 · 会话锁 · 超时 · 取消 · 事件 · 引用审计  │
└──────────────┬───────────────────────────┬──────────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────────┐   ┌──────────────────────────────┐
│ ModelGateway             │   │ ToolRegistry + ToolPolicy    │
│ LangChain 适配层         │   │                              │
│ OpenAI-compatible Model  │   │ RAG Tool                     │
└──────────────────────────┘   │ MCP Read-only Tools          │
                               │ Action Preview Tools         │
                               └──────────────────────────────┘
```

这张图中最重要的边界是：

- 上下文编译器决定模型**可以知道什么**；
- Harness 决定模型与工具**如何运行**；
- MemoryLifecycle 决定运行结果**可以留下什么**；
- 模型不能自行扩大数据源、工具权限或外部写权限。

## 3. 一轮对话如何运行

```text
用户消息
→ AgentService 创建 run_id，并以用户身份生成隔离的 session_id
→ CareerContextCompiler 识别支持模式与任务意图
→ RetrievalRouter 生成 RetrievalPlan
→ 按计划召回个人记忆与职业认知状态
→ PromptComposer 生成有来源、受限额的 System Context
→ AgentService 按策略挂载 RAG、MCP 和 Action Preview 工具
→ CareerPilotHarness 执行 Model ⇄ Tool 循环
→ AgentVerifier 检查回复与引用状态
→ MemoryLifecycle 执行记忆写入准入，并按需排队 Dreaming
→ 提取方向信号，持久化 Run 结果
→ FastAPI 通过 SSE 向前端发送增量文本和最终结果
```

`AgentService` 使用以下业务阶段记录一轮任务：

```text
CREATED → UNDERSTAND → PLAN → EXECUTE → VERIFY → LEARN → COMPLETED
                                                       └→ FAILED / CANCELLED
```

这些阶段描述“任务进行到哪里”；Harness 内部还有一套更细的 Runtime 状态，描述模型与工具如何执行。

## 4. CareerPilotHarness 执行内核

`CareerPilotHarness.stream()` 是统一执行入口，`run()` 只是消费同一事件流并返回最终结果，
因此流式和非流式调用不会维护两套 Agent 循环。

### 4.1 Runtime 状态机

```text
created → running → model ⇄ tools → completed
                       └───────→ failed / cancelled
```

Runtime 当前负责：

- 从 `SessionStore` 加载并追加持久化会话消息；
- 通过 `ContextWindowManager` 压缩过长历史；
- 使用会话级异步锁，避免同一进程内的同会话并发覆盖；
- 将当前轮动态工具叠加到 `ToolRegistry`；
- 使用 `ToolPolicy` 过滤模型可见和可调用的工具；
- 默认限制为最多四个模型步骤；
- 为模型调用和工具调用分别设置超时；
- 支持运行取消、失败终态和结构化工具错误；
- 累计模型用量并审计回答中的证据引用；
- 将 Harness 事件写入 `SqliteAgentRunStore`。

### 4.2 事件协议

```text
run.started
→ model.started
→ model.text_delta *
→ model.completed
→ [tool.requested → tool.started → tool.completed → model.started] *
→ run.completed | run.failed | run.cancelled
```

每个 `HarnessEvent` 都包含：

- `run_id`：本次 Agent 运行标识；
- `session_id`：按用户和会话隔离后的标识；
- `sequence`：单调递增的事件序号；
- `phase`：当前 Runtime 阶段；
- `step`：当前模型步骤；
- `data`：经过长度限制与清洗的 JSON 载荷。

模型消息与 Runtime 事件是两套协议：消息构成发送给模型的上下文，事件用于前端流式展示、
运行追踪、取消和评测。

## 5. 上下文、记忆与 RAG 的边界

Harness 不会自行读取所有数据。第一次模型调用前，`RetrievalPlan` 已经确定本轮允许的数据源和工具。

| 上下文层 | 当前实现 | 用途 |
|---|---|---|
| Working Context | SQLite Session + Context Window | 当前轮、近期对话和工具结果 |
| Personal Memory | 本地 Unified Memory；可选同步 MemOS | 跨会话事实、偏好、目标和经历 |
| Cognitive State | SQLite Cognitive Store | 职业假设、证据与信心 |
| Product State | Product Store | 方向、航程、任务和界面状态 |
| Career Knowledge | Governed RAG Store | 岗位、面试资料、个人文档和外部知识 |

个人记忆与 RAG 不混在一个数据池中：

- Memory 回答“关于这个用户，什么值得跨会话复用”；
- Cognitive State 回答“我们正在验证什么职业判断”；
- RAG 回答“外部世界有哪些可回源证据”；
- Product State 保存已经确认或执行的业务事实。

模型可以读取编译后的上下文，也可以调用本轮授权的只读检索工具，但不能直接写入长期记忆。
记忆写入发生在回复完成后，由 `MemoryWritePolicy` 检查稳定性、敏感度、重复和冲突。

## 6. 模型与工具边界

### ModelGateway

`ModelGateway` 接收 CareerPilot 自有的消息和工具 Schema，并输出统一的 `ModelStreamEvent`。
当前 `LangChainModelGateway` 只承担模型传输与 Tool Calling 格式适配；LangChain 的事件类型不会
进入 AgentService、API 或产品状态层。

因此，更换兼容 OpenAI 协议的模型时，不需要改变 Harness 的事件与会话协议。

### 动态工具

`AgentService` 根据当前意图为每一轮动态挂载工具：

- **RAG Tool**：查询岗位、面试资料、个人文档，并在需要时受控联网；
- **MCP Tool**：只暴露明确标记为只读、非破坏性的相关工具；
- **Action Tool**：模型只能查看授权状态和生成动作预览。

外部写操作不在 Harness 中由模型直接执行，而是通过独立的 Action Service 完成：

```text
preview → user confirm → apply → connector verify
```

确认和执行通过经过身份认证的产品 API 进行，并使用预览哈希、一次性确认和幂等键约束副作用。

## 7. 持久化与故障边界

当前使用多个 SQLite 文件隔离不同生命周期的数据：

| 存储 | 内容 |
|---|---|
| Session / Run Store | 会话消息、上下文压缩、Run、阶段、事件与检查点 |
| Memory Store | 长期记忆、证据、版本、关系与向量 |
| Cognitive Store | 职业假设与 Dreaming 队列 |
| RAG Store | 文档、Chunk、证据、岗位、全文索引与向量 |
| Product Store | 方向、罗盘、航程及其他产品状态 |
| Action Store | 授权、预览、确认、幂等记录与执行回执 |

工具失败会转化为结构化结果返回模型；模型超时、最大步数、用户取消或未处理异常会进入明确的
终态。已完成回复的记忆使用记录等遥测失败，不会反过来把成功回答变成失败。

## 8. 当前限制

本文只描述已经落地的能力。当前仍存在以下边界：

- 会话锁是进程内锁，多实例部署需要分布式并发控制；
- 默认意图解释器仍以确定性规则为主，需要用真实数据评测结构化语义分类器；
- Runtime 使用固定步数和超时限制，尚未形成完整的 Token/成本预算系统；
- 当前 `AgentVerifier` 主要校验非空回复、引用警告和运行状态，语义忠实度验证仍需增强；
- MCP 首版只允许只读工具，尚未建立完整的用户级 MCP 授权体系；
- SQLite 适合当前单机 MVP，规模扩大后需要升级并发、迁移和多实例一致性方案。

## 9. 代码入口

| 模块 | 路径 |
|---|---|
| Agent 业务编排 | `src/careerpilot/agent/service.py` |
| Harness Runtime | `src/careerpilot/harness/runtime.py` |
| 上下文编译 | `src/careerpilot/harness/context.py` |
| Runtime 事件 | `src/careerpilot/harness/events.py` |
| 会话与 Run 持久化 | `src/careerpilot/harness/session.py`、`run_store.py` |
| 工具注册与策略 | `src/careerpilot/harness/tools.py` |
| 模型适配 | `src/careerpilot/harness/model.py` |
| 记忆生命周期 | `src/careerpilot/harness/memory.py` |

## 一句话总结

CareerPilot 的 Harness 不是“又一层模型封装”，而是模型—工具循环的执行内核：
`AgentService` 决定这一轮要做什么，`CareerContextCompiler` 决定模型可以知道什么，
`CareerPilotHarness` 控制模型与工具如何运行，`MemoryLifecycle` 决定运行后可以留下什么。
