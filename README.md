# CareerPilot

面向**职业方向尚未收敛、需要长期探索的高校学生与毕业早期青年**的就业陪伴 Personal Agent。

它不以"尽快推荐更多岗位"为第一目标，而是帮助用户完成两件长期发生、彼此影响的事：

1. **慢慢摸清自己适合什么**：把零散想法、现实体验、偏好、顾虑和尝试结果组织成可修正的职业认知；
2. **在不确定和焦虑中持续行动**：先接住情绪，再把模糊想法转成一个低压力、可验证的小行动，并根据结果调整方向。

> MVP 核心闭环：`随手表达 → 被理解与整理 → 形成可验证猜想 → 用户授权小行动 → Agent 搜索/记录/提醒 → 用户反馈现实结果 → 记忆巩固与方向更新 → 每日回顾`

---

## 架构概览

CareerPilot 是一个**被严格约束的单 Agent 系统**。它把 Agent 锁在受控的 sandbox 里，只让模型做它擅长的事——基于上下文和工具观察生成回复。所有"危险"的决策（能不能用工具、什么时候搜资料、要不要写记忆）都外置到了 guard 层。

### 三层结构

```text
┌─────────────────────────────────────────────────────────────┐
│ Guard Layer（不在 Agent 循环内）                              │
│                                                              │
│  SupportPolicy.decide()                                       │
│    → 判定 support_mode + distress                            │
│    → 决定 Agent 的 allowed_tool_names                        │
│                                                              │
│  MemoryStore.search()                                         │
│    → Agent 启动前查好长期记忆                                  │
│    → 作为 <personal_memory_context> 注入 system prompt        │
│                                                              │
│  PromptComposer.compose()                                     │
│    → 组装 Skill 上下文 + 安全边界 + 记忆摘要                  │
│    → 写入 allowed_tool_names                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │ system prompt + user message + tools
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent Loop（Deep Agents / LangGraph runtime）                 │
│                                                              │
│   LLM 思考 ──▶ 需要 tool call？                               │
│        │是          │否                                      │
│        ▼            ▼                                        │
│   search_career   生成最终 AIMessage                          │
│   _knowledge                                                │
│        │                                                     │
│        ▼                                                     │
│   Tool observation ──▶ 再思考 ──▶ 循环或结束                  │
│                                                              │
│   Guardrails:                                                │
│   · listen 模式下 tools 为空                                  │
│   · 规划模式可查授权、生成外部动作预览，但不能直接执行          │
│   · apply 只存在于 API 的用户确认边界                          │
│   · 无通用 sub-agent、无 host operation                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Post-Hoc Memory Write（不在 Agent 循环内）                    │
│                                                              │
│  MemoryWritePolicy.should_write(user_message)                 │
│    → 仅稳定偏好 / 长期约束 / 明确要求记住的内容被 accepted    │
│    → 一次性情绪标签返回 skipped，不写入                        │
│    → Agent 已输出回复，不参与此决策                            │
└─────────────────────────────────────────────────────────────┘
```

### Agent 看不到的内部循环

`search_career_knowledge` tool 背后是 `AgenticRagOrchestrator`，它自己有一个**受控的 retrieve-check-expand loop**——Agent 只看到一次 tool call 和一个返回结果：

```text
Agent 调用 search_career_knowledge(query, scopes, ...)
    │
    ▼
AgenticRagOrchestrator.retrieve()
    │
    ▼
本地混合检索（Sparse + 可选 Dense + Query-to-Triple）
    │
    ▼
充分性判断 ──▶ available ──▶ 返回 hits
    │
    ▼ partial / insufficient
DashScope web search strategy=turbo
    │
    ▼
多源验证够不够？──▶ 不够 ──▶ strategy=max 再搜
    │
    ▼
返回 hits + online_sources + trace
```

Agent 不知道"本地够不够"、"搜了几轮"、"用的 turbo 还是 max"——这些决策全部封装在 tool 内部。system prompt 明确禁止 Agent 自行编排第二个 web search tool。

### 权限边界一览

| 决策 | 谁管 | Agent 能不能碰 |
|---|---|---|
| 能用什么 tool | SupportPolicy + allowed_tool_names | ✗ |
| 要不要调 search_career_knowledge | Agent 自己的思考循环 | ✓ |
| 本地搜还是联网搜 | AgenticRagOrchestrator 内部 | ✗ |
| 查用户长期记忆 | AgentService 前置注入 prompt | ✗ |
| 要不要写用户记忆 | MemoryWritePolicy 后置评估 | ✗ |
| 外部应用是否已授权 | Permission Grant + owner_id | 只能查询状态 |
| 生成外部动作预览 | ActionService.preview() | ✓ |
| 确认并执行写操作 | API confirmation boundary | ✗ |
| 用什么 system prompt | PromptComposer 启动前组装 | ✗ |

### 模块划分

```text
src/careerpilot/
├── actions/        能力目录、授权、预览/确认/执行状态机与安全 Agent tools
├── agent/          Deep Agents runtime、prompt 构建、服务编排
├── api/            FastAPI 路由与 schema（/health, /v1/chat）
├── connectors/     飞书 CLI、WPS OpenAPI、网易邮箱只读 IMAP 适配器
├── memory/         MemOS Cloud 长期记忆 + 本地 cognitive store + MemoryWritePolicy + dreaming
├── rag/            SQLite 证据索引、混合召回、RRF 重排、AgenticRagOrchestrator
├── search/         阿里云 DashScope web search（turbo → max 两级升级）
├── support/        SupportPolicy + SkillLoader
├── ingestion/      岗位信息摄取流水线（Source → Transform → Validate → Load）
└── config.py       运行时配置（pydantic-settings，从 .env 加载）
```

---

## 当前能力与边界

### 已实现

| 能力 | 说明 |
|---|---|
| 四种支持模式 | `listen` / `organize` / `explore` / `act`，用户显式选择优先 |
| 情绪优先 | 有负面情绪时先提供具体慰藉，不把"能行动"误判为"应该行动" |
| 长期记忆 | MemOS 搜索在模型调用之前、写入在完整回复之后；返回读写状态供前端展示 |
| 记忆写入策略 | 一次性的难受、自责和情绪标签不进入长期记忆（返回 `skipped`）；仅稳定偏好 / 长期约束 / 明确要求记住的内容被接受 |
| 优雅降级 | MemOS 不可用时降级为当前会话回复，不伪造"记得" |
| Agent Harness | Deep Agents 作为 runtime；MVP 禁用 generic sub-agent 和 host operation tools |
| LLM | 通过阿里云百炼 OpenAI-compatible API 使用 Qwen，生产默认固定 `qwen3.7-plus-2026-05-26` |
| Web Search | 本地 RAG 证据不足或用户明确询问实时信息时，调用 DashScope web search；默认 `turbo`，多源验证不足时升级 `max`，不叠加第二层搜索 Agent |
| 统一 RAG | 统一 Evidence Unit 索引（Passage / KG 三元组 / 表格事实共一个 SQLite 文件） |
| 混合召回 | 默认 Sparse + 可选 Dense，Query-to-Triple 轻量关系扩展；RRF + 来源等级 + 证据角色重排，最多两轮 |
| 网页摄取 | 来源注册表支持按 URL 设置刷新周期；搜索已接入，网页全文抓取与定时入库属于后续受治理任务 |
| 外部授权可见性 | 按用户、provider、capability 展示 `granted` / `not_granted`，支持即时撤权 |
| 飞书 | 创建云文档、创建日程；通过官方 `lark-cli`，固定参数数组且不使用 shell |
| WPS | 在配置的 drive/parent 下创建文档文件 |
| 网易邮箱 | 只读搜索招聘邮件元数据；不读取正文、不发送邮件 |
| 动作治理 | 写操作严格走 Preview → Confirm → Apply → Verify；确认令牌单次使用，幂等回执防重复执行 |

### 不在本阶段

- Dreaming Worker（跨会话记忆整合）
- PostgreSQL 产品状态（当前 RAG + Memory 均为 SQLite 单文件）
- QQ 邮箱、微信连接器与邮件发送
- WPS 富文本正文编辑、跨 provider 工作流和主动调度
- 生产级多用户 OAuth 回调、加密 token vault 与正式账号登录

> ⚠️ 当前接口使用服务端签名的 HttpOnly owner cookie 做本地纵向切片隔离，但尚不是正式账号登录。环境变量凭据仅适合单机开发，不应直接暴露到公网或用于多租户部署。

---

## 快速开始

**要求**：Python 3.12、[uv](https://docs.astral.sh/uv/)。

### 1. 安装依赖

```powershell
uv sync --group dev
Copy-Item .env.example .env
```

### 2. 配置环境变量

在 `.env` 中填入以下密钥（均使用被 Git 忽略的本地文件；线上使用云平台 Secret）：

| 变量 | 说明 |
|---|---|
| `MEMOS_API_KEY` | MemOS Cloud 密钥 |
| `CAREERPILOT_MODEL_BASE_URL` | 百炼工作空间的 OpenAI 兼容地址 |
| `CAREERPILOT_MODEL_API_KEY` | 百炼 API Key |
| `CAREERPILOT_MODEL_NAME` | 生产固定 `qwen3.7-plus-2026-05-26` |
| `CAREERPILOT_EXPLORATION_TEMPERATURE` | 探索/改写温度，默认 `0.4` |
| `CAREERPILOT_REASONING_TEMPERATURE` | 证据规划与判断温度，默认 `0.0` |
| `CAREERPILOT_EMBEDDING_MODEL` | 可选 Dense Embedding 模型；未配置时自动 Sparse + 图关系模式 |
| `DASHSCOPE_API_KEY` | 联网搜索百炼 Key |
| `CAREERPILOT_DASHSCOPE_BASE_URL` | 同一工作空间的 DashScope `/api/v1` 地址 |
| `CAREERPILOT_SEARCH_MODEL` | 默认与主模型同一快照 |
| `CAREERPILOT_SEARCH_DEFAULT_STRATEGY` | 固定 `turbo` |
| `CAREERPILOT_SEARCH_ESCALATION_STRATEGY` | 固定 `max` |
| `CAREERPILOT_ACTION_DB_PATH` | owner 隔离的授权、动作预览、确认与回执 SQLite 文件 |
| `CAREERPILOT_FEISHU_CLI_EXECUTABLE` | 官方 `lark-cli` 可执行文件；需先完成用户授权 |
| `CAREERPILOT_WPS_ACCESS_TOKEN` | 本机 MVP 的 WPS token；同时配置 drive/parent 才启用 |
| `CAREERPILOT_NETEASE_ACCOUNT` | 网易邮箱账号；同时配置客户端授权码才启用只读搜索 |

百炼控制台会给出同一工作空间的两个不同地址：

```dotenv
CAREERPILOT_MODEL_BASE_URL=https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
CAREERPILOT_DASHSCOPE_BASE_URL=https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
```

> 不要把真实 Key 写入 `.env.example`、README、Dockerfile 或前端环境变量。若 Key 曾出现在截图、聊天记录或日志中，联调完成后应在百炼控制台轮换。

### 外部应用授权与动作边界

MVP 的 Agent 只看到四个稳定领域能力：

| Provider | Capability | 风险 | 每次确认 |
|---|---|---:|---|
| 飞书 | `document.create` | L3 写 | 是 |
| 飞书 | `calendar.create` | L3 写 | 是 |
| WPS | `document.create` | L3 写 | 是 |
| 网易邮箱 | `email.search_recruiting` | L1 只读 | 否（仍须先授权） |

授权与动作 API：

- `GET /v1/me/integrations`：查看每项能力是否已授权；
- `POST /v1/me/integrations/{provider}/grants`：记录用户明确授予的能力与用途；
- `DELETE /v1/me/integrations/{provider}/grants/{grant_id}`：即时撤权；
- `POST /v1/me/actions/preview`：规范化并冻结动作预览；
- `POST /v1/me/actions/{id}/confirm`：把一次性确认令牌绑定到预览哈希；
- `POST /v1/me/actions/{id}/apply`：带幂等键执行并返回 `completed` / `failed` / `unknown` 回执。

写操作在执行前和执行时都会重新检查授权。Agent 本身只有“查看授权”和“生成预览”两个工具，没有 apply 工具；真正执行必须经过产品 API 的用户确认边界。外部数据不会自动写入 MemOS。

本机飞书接入先按[官方 Lark CLI](https://github.com/larksuite/cli)安装并登录；WPS 使用[开放平台服务端 API](https://open.wps.cn/documents/app-integration-dev/guide/overview)。生产环境不得继续使用共享环境变量保存用户 token/邮箱授权码，应改为 OAuth 回调、owner 绑定和加密 token vault。

### 3. 构建本地知识索引

```powershell
.venv\Scripts\python.exe scripts\build_rag_index.py `
  --markdown-dir data\rag\sources\jobs
```

如需 Dense 检索，在 `.env` 中配置 `Qwen/Qwen3-Embedding-0.6B` 或其他兼容模型。第一版不会自动下载本地模型，也不强制部署 Neo4j、Milvus 或独立重排服务。

增量摄取岗位信息：

```powershell
.venv\Scripts\python.exe scripts\ingest_job_records.py data\incoming\jobs.json
```

岗位检索与核验规则位于 `skills/career-job-intelligence/`。流水线采用 Source → Transform → Validate → Load 分层，相同内容只更新抓取时间，不重复切分或生成向量。

### 4. 启动 API

```powershell
uv run uvicorn careerpilot.api.app:app --reload --port 8080
```

### 5. 调用示例

```powershell
$body = @{
  conversation_id = "demo-thread"
  message = "我投了很多简历都没回应，现在只想先说说"
  support_mode = "listen"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8080/v1/chat" `
  -ContentType "application/json" `
  -Body $body
```

返回结构：

```json
{
  "reply": "...",
  "support_mode": "listen",
  "memory_read_status": "available",
  "memory_write_status": "skipped"
}
```

### 联网检索边界（工具内部，Agent 不可见）

```text
AgenticRagOrchestrator.retrieve()
  ├─ 本地检索 available：直接返回 hits
  ├─ partial：DashScope turbo 联网搜索
  └─ insufficient：turbo + max 升级搜索
```

联网搜索返回标题、URL、站点、策略与请求 ID，统一标记为不可信外部证据。搜索结果不会写入个人 Memory，也不会在工具内部自动污染 RAG。listen 模式下 Agent 看不到 `search_career_knowledge` 这个工具，整个检索循环不会启动。

---

## 开发与验证

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check src tests
```

---

## 文档索引

| 文档 | 内容 |
|---|---|
| `PRD/CareerPilot-MVP-PRD.md` | MVP 产品需求：背景、用户画像、核心闭环、竞品分析 |
| `PRD/CareerPilot-Memory-RAG-Technical-Design.md` | 长期记忆、Dreaming、Agentic RAG 技术设计 |
| `PRD/CareerPilot-RAG-MVP-Design.md` | RAG MVP 检索 Skill、统一 Markdown、切分与索引方案 |
| `skills/career-job-intelligence/SKILL.md` | 岗位智能 Skill 规格 |
| `skills/career-emotional-support/SKILL.md` | 情绪陪伴 Skill 规格 |
