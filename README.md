# CareerPilot

CareerPilot 是面向职业方向尚未确定人群的长期就业陪伴 Personal Agent。当前后端纵向切片已经串通：

```text
POST /v1/chat
  → 情绪陪伴模式判定
  → MemOS 用户级长期记忆召回
  → CareerPilot Skill 与安全上下文组装
  → Deep Agents 模型循环
  → 仅将稳定偏好/长期约束/明确要求记住的候选内容回写 MemOS
```

## 当前能力

- `listen / organize / explore / act` 四种支持模式，用户显式选择优先；
- 有负面情绪时先提供具体慰藉，不把“能行动”误判为“应该行动”；
- MemOS 搜索在模型调用之前、写入在完整回复之后，并返回读写状态；
- 一次性的难受、自责和情绪标签不进入长期记忆，返回 `memory_write_status=skipped`；
- MemOS 不可用时降级为当前会话回复，不伪造“记得”；
- Deep Agents 作为 Harness；MVP 禁用通用子 Agent 和宿主机操作工具；
- 通过 OpenAI-compatible API 使用 Qwen，默认模型标识为 `Qwen/Qwen3.8-27B`。
- 统一 Evidence Unit RAG：Passage、KG 三元组、表格事实/行使用同一 SQLite 索引；
- 默认执行 Sparse + 可选 Dense 混合召回，并用 Query-to-Triple 做轻量关系扩展；
- 使用 RRF、来源等级和证据角色重排，最多两轮，无新证据时停止并请求联网补充；
- 网页来源注册表支持按 URL 设置刷新周期，抓取执行仍由外部 Search/Fetch Skill 负责。

Dreaming Worker、PostgreSQL 产品状态、飞书 Tool 与 Web 前端仍属于下一阶段，尚未伪装成已完成能力。

> 当前接口是本地开发纵向切片，`user_id` 尚未由登录会话签发。接入鉴权与服务端用户
> 隔离之前，不应直接暴露到公网。

## 本地启动

要求：Python 3.12、[uv](https://docs.astral.sh/uv/)。

```powershell
uv sync --group dev
Copy-Item .env.example .env
```

在 `.env` 中配置：

- `MEMOS_API_KEY`：MemOS Cloud 密钥；
- `CAREERPILOT_MODEL_BASE_URL`：本地 vLLM 或云端 OpenAI-compatible 地址；
- `CAREERPILOT_MODEL_API_KEY`：模型服务密钥；
- `CAREERPILOT_MODEL_NAME`：服务端加载的 Qwen 模型标识。
- `CAREERPILOT_EXPLORATION_TEMPERATURE`：探索/改写温度，默认 `0.4`；
- `CAREERPILOT_REASONING_TEMPERATURE`：证据规划与判断温度，默认 `0.0`；
- `CAREERPILOT_EMBEDDING_MODEL`：可选的 OpenAI-compatible Embedding 模型；未配置时自动使用 Sparse + 图关系模式。

构建本地知识索引：

```powershell
.venv\Scripts\python.exe scripts\build_rag_index.py `
  --markdown-dir data\rag\sources\jobs
```

如需 Dense 检索，可在 `.env` 中配置 `Qwen/Qwen3-Embedding-0.6B` 或其他兼容模型。
第一版不会自动下载本地模型，也不强制部署 Neo4j、Milvus 或独立重排服务。

将岗位搜索 Skill 输出的 JSON 增量加入知识库：

```powershell
.venv\Scripts\python.exe scripts\ingest_job_records.py data\incoming\jobs.json
```

岗位检索与核验规则位于 `skills/career-job-intelligence/`。它区分官方来源、线索来源、
单位性质和用工/编制类型；相同内容只更新抓取时间，不重复切分或生成向量。该轻量流水线
采用 Source → Transform → Validate → Load 分层，不需要部署完整 Mage 服务。

启动 API：

```powershell
uv run uvicorn careerpilot.api.app:app --reload --port 8080
```

调用示例：

```powershell
$body = @{
  user_id = "demo-user"
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

## 验证

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check src tests
```

产品规格见 `PRD/CareerPilot-MVP-PRD.md`，记忆与 Agentic RAG 技术设计见
`PRD/CareerPilot-Memory-RAG-Technical-Design.md`；RAG MVP 的两个检索 Skill、统一
Markdown、开发者上传、切分与索引方案见 `PRD/CareerPilot-RAG-MVP-Design.md`。
