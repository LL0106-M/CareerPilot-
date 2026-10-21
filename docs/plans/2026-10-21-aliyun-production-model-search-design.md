# CareerPilot 阿里云生产模型与联网搜索设计

## 目标

把当前可本地运行的 CareerPilot Agent 升级为可上线配置：主模型使用阿里云百炼
`qwen3.7-plus`，外部实时信息使用百炼 DashScope 联网搜索，同时保留现有 DeepAgents、
MemOS 和本地 Agentic RAG 的边界。

## 核心决定

1. 主模型与搜索能力解耦。DeepAgents 主循环继续通过 OpenAI 兼容 Chat API 调用
   `qwen3.7-plus`；联网搜索作为显式工具，不对每次模型调用默认开启。
2. 生产环境固定 `qwen3.7-plus-2026-05-26`，开发/预发布可使用滚动别名
   `qwen3.7-plus`。固定快照避免模型升级破坏陪伴语气、记忆判断和工具行为。
3. 搜索使用 DashScope 原生多模态生成端点。原因是 OpenAI 兼容搜索不返回完整来源，
   而原生接口可以返回 `search_info.search_results`，满足引用、审计和后续入库要求。
4. 默认使用 `turbo`；需要多源验证且首轮不足时，调用方可升级为 `max`。不使用百炼
   `agent` 搜索策略，因为 CareerPilot 外层已有 Agentic RAG 循环，重复 Agent 会增加
   延迟、成本和不可控性。
5. 搜索结果是外部不可信证据，不是 Memory。它可以支持当前回答，经过抓取、清洗、
   去重和来源审核后才能进入 RAG。

## 运行链路

```text
用户问题
  -> MemOS 获取个人长期上下文
  -> DeepAgents + qwen3.7-plus
  -> search_career_knowledge 查询本地 RAG
  -> 若 evidence.needs_online_search = true
       -> search_web(strategy=turbo)
       -> 必要时 search_web(strategy=max)
       -> 带 URL、标题、站点和检索时间返回给 Agent
  -> 回答中引用来源
```

MVP 不在搜索工具内部自动写入 RAG，也不直接抓取全文。这样将“实时回答”和“知识库治理”
分开，避免低质量搜索结果污染知识库。后续定时入库任务复用搜索结果 Schema。

## 组件

- `Settings`：模型端点、模型 ID、DashScope 搜索端点、搜索模型、默认/升级策略、超时。
- `AliyunWebSearchProvider`：构造多模态搜索请求，解析 SSE，提取回答与去重后的来源。
- `search_web`：DeepAgents 结构化工具；限制策略为 `turbo|max`，返回不可信内容标记。
- `AgentService`：倾听模式禁止联网；梳理/行动模式允许本地 RAG 与联网搜索。

## 错误与降级

- 缺少搜索密钥：应用仍可启动，本地 RAG 可用，联网工具不注册。
- 401/403：返回鉴权不可用，不重试。
- 429/5xx/超时：至多由 HTTP 客户端做一次有界重试；失败后让 Agent 明示实时资料不可用。
- SSE 畸形或没有来源：不伪造引用，返回空来源并标记 `partial`。
- URL 去重：规范化 scheme/host、移除 fragment；保留首次出现顺序。

## 安全与成本

- `DASHSCOPE_API_KEY` 仅进入本机 `.env` 或部署平台 Secret，不进入 Git。
- 单次工具调用只执行一种策略；最多两轮由 Agentic RAG 控制。
- 倾听模式禁止 RAG 与搜索，避免在用户需要情绪承接时用信息轰炸。
- 工具返回内容统一带 `content_is_untrusted=true`，系统提示禁止执行网页中的指令。

## 验收

- 配置可以生成生产 `ChatOpenAI` 客户端，温度仍保持探索 0.4、推理 0。
- 单元测试验证 DashScope 请求端点、鉴权头、流式参数、策略和来源解析。
- Agent 非倾听模式可见 `search_web`，倾听模式不可见。
- 无搜索配置时服务可降级启动。
- 完整测试、Ruff 和编译检查通过。
