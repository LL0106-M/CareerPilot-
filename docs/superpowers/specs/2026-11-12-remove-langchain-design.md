# CareerPilot 移除 LangChain 设计

## 背景与意图

CareerPilot 已经拥有自己的 Agent Harness、模型合同、工具合同、会话存储、运行状态和安全边界。LangChain 当前没有承担 Agent 编排，只提供 `ChatOpenAI`、消息对象、`StructuredTool` 和 `OpenAIEmbeddings` 等薄包装。这使模型和工具在进入 CareerPilot 自有合同前多经过一层转换，并让代码看起来像存在两个运行时。

本次改造选择完整移除 LangChain，直接使用官方 OpenAI Python SDK 连接 Qwen/OpenAI-compatible API，并让 RAG、Search、Actions 和 MCP 直接实现 CareerPilot 的 `HarnessTool` 合同。

## 目标

- `CareerPilotHarness` 保持唯一 Agent 运行时。
- 使用官方 `openai` SDK 完成聊天、流式输出、Tool Calling 和 Embedding。
- 所有运行时工具直接实现 `HarnessTool`，不再经过 `BaseTool` / `StructuredTool`。
- 保持现有用户可见行为、模型配置、工具名称、参数 Schema、安全策略和持久化行为。
- 完整删除生产代码、测试和项目依赖中的 LangChain 引用。
- 保持 provider-neutral 的 `ModelGateway` 与 `EmbeddingProvider` 合同，避免 Harness 绑定具体 SDK。

## 非目标

- 不在本次重构中重新设计 MCP 授权、Resources 或 Prompts。
- 不增加新的业务工具或 MCP Server。
- 不改变 Actions 的 preview-confirm-apply 边界。
- 不引入 LangGraph、OpenAI Agents SDK 或新的 Agent 框架。
- 不改变提示词、意图识别、记忆写入策略或 RAG 排序算法。
- 不借本次重构修改已有搜索功能或用户配置语义。

## 反目标

- 不在 Harness 之外创建第二个 Tool Calling 循环。
- 不用手写 HTTP/SSE 协议替代官方 SDK。
- 不用兼容包装保留长期的 LangChain 类型泄漏。
- 不允许原生工具绕过现有 ToolPolicy、McpToolPolicy 或 ActionService。

## 约束

- Python 3.12。
- 当前模型服务使用 OpenAI-compatible Chat Completions 接口。
- 当前锁文件已间接安装 `openai 3.35.1`；改造后将其改为直接项目依赖并移除 `langchain-openai`。
- Embedding 当前是同步合同，聊天模型是异步合同；本次保持这一调用形状，避免扩大 RAG 存储层改动。
- 流式调用必须正确合并分片文本和分片 Tool Call 参数。
- 工具调用 ID、finish reason、usage 和空响应错误语义必须保持。
- 工作区已有与本重构无关的用户修改，实施不得覆盖或回退。

## 考虑过的方案

### 方案一：只移除工具侧 LangChain

优点是改动较小；缺点是模型、Embedding、Memory 分析器和评测仍泄漏 LangChain 类型，长期形成半迁移状态。未选择。

### 方案二：官方 OpenAI SDK + CareerPilot 原生合同

模型和 Embedding 使用官方 SDK，业务工具直接实现 `HarnessTool`，Harness 继续拥有循环和状态。它删除重复抽象，同时保留成熟的协议、流式和错误处理实现。已选择。

### 方案三：使用 httpx 自研 OpenAI-compatible 协议

依赖最少，但需要自行维护 SSE、Tool Call 分片、重试、错误分类和协议兼容。维护成本高于收益。未选择。

## 目标架构

```text
AgentService
    |
    v
CareerPilotResponder
    |
    v
CareerPilotHarness ----------------------- 唯一 Agent 循环
    |                       |
    |                       +--> ToolRegistry
    |                              |-- RAG HarnessTool
    |                              |-- Search HarnessTool
    |                              |-- Action HarnessTool
    |                              `-- MCP HarnessTool
    |
    `--> OpenAICompatibleModelGateway
              |
              `--> AsyncOpenAI --> Qwen/OpenAI-compatible API

RAG ingestion/query
    `--> OpenAICompatibleEmbeddingProvider
              `--> OpenAI --> Embedding API
```

依赖方向固定为：业务层依赖 CareerPilot 合同，Provider/工具适配器实现这些合同；任何 CareerPilot 核心模块不得依赖 LangChain 类型。

## 模型层设计

### 客户端创建

`agent/model.py` 不再返回 `ChatOpenAI`，而是构造实现 `ModelGateway` 的 `OpenAICompatibleModelGateway`。该 Gateway 内部持有 `AsyncOpenAI`，配置沿用现有：

- `api_key`
- `base_url`
- `model`
- `temperature`
- `timeout`
- `max_retries=1`

探索、推理和 Dreaming 模型工厂继续存在，并通过不同 temperature/timeout 返回独立 Gateway。`create_qwen_model` 可继续作为向后兼容别名，但返回类型改为 `ModelGateway`。

### 消息转换

Gateway 将 `HarnessMessage` 转换为 OpenAI-compatible message 字典：

- system/user：普通 `content`。
- assistant：`content` 加可选 `tool_calls`。
- tool：`tool_call_id`、`name` 和 `content`。

工具 Schema 从 `ToolSchema` 转换为 `type=function`、`name`、`description`、`parameters`。Harness 合同继续是唯一内部真源。

### 非流式响应

`generate()` 调用 Chat Completions API，规范化首个 choice 为 `ModelResponse`：

- 文本内容归一化为字符串。
- Tool Call arguments 从 JSON 字符串解析为对象；非对象或无效 JSON 产生明确 provider error，不进入工具执行。
- 缺失 Tool Call ID 时生成稳定的本次响应内回退 ID。
- 读取 finish reason 与 usage；缺失字段时使用空值而不是猜测。
- 没有文本且没有 Tool Call 时由现有 Harness 判为错误。

### 流式响应

`stream()` 使用官方 SDK streaming API：

- 文本 delta 立即转换为 `ModelStreamEvent(text_delta=...)`。
- Tool Call 按 choice/index 聚合 ID、name 和 arguments 字符串片段。
- 流结束后解析聚合后的 arguments 并产生唯一的最终 `ModelResponse` 事件。
- usage 仅在 Provider 返回时记录；缺失 usage 与当前行为一样被允许，不构成运行失败。
- 不强制发送仅为流式 usage 服务的 Provider 特有选项，避免 OpenAI-compatible Qwen 端点因不支持该选项而拒绝请求；如果端点自然返回 usage，则正常归一化记录。
- 空流、非法 Tool Call JSON 和 Provider 异常转换为清晰异常，交给 Harness 现有失败路径处理。

不在 Gateway 内实现 Agent 重试循环；SDK 网络重试与 Harness 的模型步骤上限职责分开。

## 非 Harness 的模型调用

`JsonDreamingAnalyzer`、`JsonDirectionSignalDetector`、`LLMQualityJudge` 不再接收 `BaseChatModel`。它们改为依赖一个窄的 CareerPilot 文本生成合同，或者直接复用 `ModelGateway.generate()`：

```python
ModelRequest(messages=(system_message, user_message))
```

选择复用 `ModelGateway`，避免再创建第二套模型接口。这些调用不传工具，保持当前结构化 JSON 解析逻辑。

## 工具层设计

### 原生工具实现

新增一个小型通用实现，例如 `FunctionHarnessTool`：

- 持有 `ToolSchema`。
- 持有同步或异步 handler。
- 在 `execute(arguments)` 中调用 handler，并把结果规范化为字符串。
- handler 异常包装成 `ToolExecutionError`，不暴露敏感原始异常。

参数 Schema 使用显式 JSON Schema。为了保持可审计性，不引入新的自动函数反射框架。

### ToolRegistry

删除：

- `LangChainToolAdapter`
- `ToolRegistry.from_langchain`
- 接收 `BaseTool` 的 `overlay`

替换为：

- `ToolRegistry(tools: tuple[HarnessTool, ...])`
- `overlay(tools: tuple[HarnessTool, ...])`

保留现有 `ToolPolicy`、未知工具、禁止工具和结构化失败语义。重名工具的行为在实施时改为显式拒绝，避免后注册工具静默覆盖现有工具。

### RAG 与 Search

`build_rag_tool`、`build_agentic_rag_tool`、`build_web_search_tool` 返回 `HarnessTool`。工具名称、描述、参数字段、默认值和 JSON 输出保持现状。

原有通过 `.ainvoke({...})` 测试的调用改为 `.execute({...})`；业务断言保持不变。

### Actions

`build_action_tools` 返回两个 `HarnessTool`：

- `get_integration_authorization`
- `preview_external_action`

它们仍然只能查询授权或创建预览，不能直接 apply。用户确认和真实副作用仍由现有产品/API 边界完成。

### MCP

`McpToolAdapter` 直接实现或生成 `HarnessTool`：

- Schema 来自 `McpToolDescriptor.input_schema`。
- 执行前继续调用 `McpToolPolicy.allows()`。
- 调用 `McpClientProtocol.call_tool()`。
- 保留 namespaced name、结果截断、`content_is_untrusted` 和结构化状态。

`McpToolPlatform.runtime_tools()` 返回 `tuple[HarnessTool, ...]`，本次不改变选择算法和只读安全策略。

## Embedding 设计

用官方同步 `OpenAI` 客户端替换 `OpenAIEmbeddings`：

- 批量调用 `client.embeddings.create(model=..., input=batch, encoding_format="float")`。
- 按响应 index 恢复与输入相同的向量顺序。
- `embed_query` 继续添加当前 instruct 前缀。
- 空输入返回空列表。
- 响应数量不匹配或缺失向量时明确失败。
- `EmbeddingProvider` 协议保持同步，避免本次修改所有 RAG 调用方。

## 类型和装配变化

下列工厂和端口从 LangChain 类型改为 CareerPilot 类型：

- `CareerPilotResponder(model: ModelGateway, tools: list[HarnessTool] | None)`
- `AgentResponder.runtime_tools: tuple[HarnessTool, ...]`
- `McpToolFactory -> Awaitable[tuple[HarnessTool, ...]]`
- `rag_tool_factory -> HarnessTool`
- `action_tool_factory -> tuple[HarnessTool, ...]`
- `build_agent_tools() -> list[HarnessTool]`

`CareerPilotResponder` 不再构造 `LangChainModelGateway`，而是直接把已构造的 `ModelGateway` 交给 Harness。

## 错误处理与安全

- Provider 认证、连接、超时和限流异常不得泄露 API Key 或完整响应体。
- 无效模型 Tool Call 参数不得进入工具执行器。
- MCP 返回内容继续标记为不可信。
- Action 工具不能获得真实 apply 能力。
- Harness 继续拥有模型超时、工具超时、最大步数和取消语义。
- 工具结果和事件继续通过现有敏感字段清洗与长度限制。

## 测试策略

### 模型 Gateway

- 使用官方 SDK 支持的 mock transport/注入客户端，不访问网络。
- 覆盖文本响应、单/多 Tool Call、非法 JSON 参数、usage、finish reason。
- 覆盖流式文本、分片 Tool Call、多 Tool Call 交错和空流。

### 工具

- `FunctionHarnessTool` 同步/异步执行、结果规范化和异常包装。
- RAG/Search/Actions/MCP 保持现有业务断言。
- ToolRegistry 覆盖 allow/deny/not-found/duplicate。

### Embedding

- 批处理、顺序恢复、query instruction、空输入和异常响应。

### 回归

- 运行完整 Python 测试套件。
- 运行 Ruff。
- 搜索生产代码、测试、依赖和锁文件，确认不存在 `langchain`、`BaseTool`、`StructuredTool`、`ChatOpenAI`、`OpenAIEmbeddings`。
- 运行现有离线系统 benchmark，以 `evals/reports/2026-11-05-system-benchmark-v1.json` 为冻结基线：RAG Pass Rate 不低于 87.5%，Memory Pass Rate 保持 100%，硬失败保持 0。延迟仅记录和对比，不作为这次 Provider/工具适配重构的硬门槛，因为它受本机负载影响。

## 迁移顺序

1. 先增加原生 OpenAI Gateway 及其测试，但暂不切换装配。
2. 增加原生 `FunctionHarnessTool`，迁移 ToolRegistry。
3. 依次迁移 Search、RAG、Actions、MCP。
4. 切换 `AgentService`、Responder 和 API dependencies 的类型与装配。
5. 迁移 Dreaming、Direction Signals 和 Eval 的模型调用。
6. 迁移 Embedding。
7. 删除所有 LangChain adapter、依赖和测试替身。
8. 更新锁文件并执行全量验证。

每一步保持测试可运行；不保留双栈运行开关。Git 历史本身提供回滚，不增加产品级兼容配置。

## 完成标准

- `pyproject.toml` 直接依赖兼容版本的 `openai`，不依赖任何 LangChain 包。
- `src/` 与 `tests/` 不包含 LangChain 类型或导入。
- Harness 是唯一模型/工具循环。
- 所有现有工具名称、参数和安全行为保持。
- 完整测试、Ruff 和离线 benchmark 通过。
- 不修改或覆盖工作区中与本重构无关的已有改动。

## 留给实施者的局部决策

- 原生 Gateway、工具辅助类的具体文件拆分，只要依赖方向满足本文约束。
- OpenAI SDK 测试替身的具体实现方式。
- 内部异常类名称和日志字段名称，只要不改变用户可见错误及安全边界。
