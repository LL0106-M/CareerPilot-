# CareerPilot 用户私有资料与个人档案设计

日期：2026-10-21
状态：待用户复核

## 1. 目标

为 CareerPilot 增加可上线的用户资料闭环：用户上传简历、个人陈述等文件后，系统将原始文件保存到云端私有存储，异步解析并建立用户级私有检索索引，从文件中提取带来源的个人档案候选，经用户确认后供 Agent 做岗位匹配、材料修改和长期职业探索。

成功标准：

- 用户可以上传、查看、替换和删除自己的资料；
- 任一用户无法读取、搜索或推断其他用户的资料；
- Agent 能按当前任务检索用户资料，并引用文件版本和页码/段落；
- 模型提取的个人信息在确认前不得作为确定事实；
- 删除文件会传播到原文、切片、索引和未确认候选；
- 公共 RAG、私有资料、结构化档案和 MemOS 长期记忆保持清晰边界。

## 2. 已确认决策

- 云端基础设施采用 Supabase：PostgreSQL、pgvector、Storage、Auth 和 Row Level Security。
- 第一版支持 PDF、DOCX、TXT；扫描件和图片 OCR 不在第一版范围内。
- 文件处理采用异步任务状态，不在上传请求中执行完整解析与 Embedding。
- 用户资料使用独立的私有检索域，不进入公共岗位或备考资料索引。
- 文件解析结果先生成 `profile_claims`；只有用户确认后才写入 `profile_facts`。
- 简历正文和提取字段不会自动写入 MemOS。MemOS 继续负责对话中形成的长期偏好、目标和互动方式。
- API 从 Supabase Auth 身份中取得 `user_id`，不信任请求体中的用户标识。

## 3. 系统边界

```text
Personal Agent Harness
├─ Context Router
├─ Context Compiler
├─ Personal Memory Controller        MemOS
├─ Shared Knowledge Controller       公共岗位/备考 RAG
├─ Private Corpus Controller         用户文件与私有检索
├─ Structured Profile Controller     已确认个人档案
└─ Policy / Auth / Audit
```

各系统职责：

| 系统 | 真相来源 | 内容 |
|---|---|---|
| Supabase Storage | 原始文件真相源 | 简历、个人陈述和其他用户上传文件 |
| Private Corpus | 可追溯的私有文档索引 | 文档切片、页码/段落、Embedding |
| Structured Profile | 用户确认的结构化事实 | 教育、经历、项目、技能、证书和求职约束 |
| MemOS | 对话长期记忆 | 明确偏好、长期目标、重要经历和支持方式 |
| Shared RAG | 公共知识 | 岗位、政策、备考资料和职业知识 |
| Product State | 确定性业务状态 | 当前简历版本、收藏岗位、投递和资料处理状态 |

同一内容可以建立可追溯关系，但不能在系统之间静默复制。例如，简历中的项目经历可形成待确认档案候选；确认后成为结构化档案事实，但不会因此自动成为 MemOS 记忆。

## 4. 数据流

```text
Authenticated Upload
→ 文件签名、类型、大小和配额校验
→ 计算 SHA-256，建立 document/version
→ 上传 Supabase private bucket
→ 创建 ingestion_job，返回 202
→ Worker 提取文本和位置
→ 切分、Embedding、写入私有 pgvector 索引
→ LLM 结构化提取 profile_claims
→ 用户查看证据并确认/修改/拒绝
→ 写入版本化 profile_facts
→ Agent 按任务装配 Profile + Private Corpus Context
```

状态机：

```text
uploaded → parsing → indexing → review_required → ready
              └──────────────→ failed
ready → replacing → ready
任意可删除状态 → deleting → deleted
```

失败任务保留错误码、阶段和重试次数，不在日志中保存原始正文。

## 5. Supabase 存储设计

### 5.1 Storage

私有 Bucket：`careerpilot-user-documents`。

对象路径固定为：

```text
{tenant_id}/{user_id}/{document_id}/{version_id}/{sanitized_filename}
```

Bucket 禁止公开访问。下载和预览只通过短期签名 URL；服务端仍需先验证资源属于当前登录用户。

### 5.2 PostgreSQL 表

`user_documents`

- `id`, `tenant_id`, `user_id`
- `kind`: `resume|personal_statement|portfolio|certificate|other`
- `title`, `status`, `current_version_id`
- `created_at`, `updated_at`, `deleted_at`

`document_versions`

- `id`, `document_id`, `tenant_id`, `user_id`, `version_number`
- `storage_path`, `original_filename`, `mime_type`, `size_bytes`, `sha256`
- `parser_version`, `embedding_version`, `status`
- `created_at`, `superseded_at`

`document_chunks`

- `id`, `document_version_id`, `tenant_id`, `user_id`
- `ordinal`, `page_number`, `section_path`, `content`
- `content_hash`, `embedding`, `metadata`
- PostgreSQL 全文索引和 pgvector 索引

`profile_claims`

- `id`, `tenant_id`, `user_id`, `document_version_id`
- `field_path`, `value_json`, `normalized_value_json`
- `evidence_chunk_ids`, `confidence_band`
- `status`: `pending|accepted|edited|rejected|superseded`
- `extractor_version`, `created_at`, `reviewed_at`

`profile_facts`

- `id`, `tenant_id`, `user_id`, `field_path`, `value_json`
- `source_claim_id`, `source_document_version_id`, `evidence_chunk_ids`
- `status`: `active|superseded|disputed|deleted`
- `version`, `created_at`, `updated_at`

`document_ingestion_jobs`

- `id`, `document_version_id`, `tenant_id`, `user_id`
- `stage`, `status`, `attempt_count`, `error_code`
- `idempotency_key`, `started_at`, `finished_at`

所有用户表启用 RLS，并同时用 `tenant_id + user_id` 过滤。后台 Worker 使用受限服务身份，业务查询仍显式携带并校验用户作用域。

### 5.3 Worker 调度

第一版不引入额外消息队列。独立 Worker 轮询 `document_ingestion_jobs`，通过 PostgreSQL `FOR UPDATE SKIP LOCKED` 原子领取任务，并使用 `idempotency_key` 防止重复处理。任务采用有上限的指数退避；超过最大次数后进入 `failed`，只能由用户或运维显式重试。API 进程不在后台线程中执行解析，避免进程重启导致任务静默丢失。

## 6. 上传与解析规则

第一版默认限制：单文件 15 MB，每用户最多 100 个有效文件；限制值通过环境变量配置。

校验顺序：

1. 验证登录身份和用户配额；
2. 同时检查扩展名、声明 MIME 和文件签名；
3. 拒绝加密 PDF、宏文档、可执行内容和畸形压缩包；
4. 计算 SHA-256；同一用户上传相同内容时复用已有版本或返回重复提示；
5. 写数据库 pending 记录后上传 Storage；任一步失败进入可补偿状态；
6. DOCX 只读取文本、表格和标题，不执行宏或外部链接；
7. PDF 保存页码，DOCX/TXT 保存段落和章节定位；
8. 无可提取文本的扫描件标记为 `ocr_required`，不生成空档案。

第一版解析器：PDF 使用 `pypdf`，DOCX 使用 `python-docx`，TXT 只接受 UTF-8 或可安全检测的文本编码。

## 7. 档案提取与审核

允许提取的档案域：

- 基本职业信息；
- 教育经历；
- 工作和实习经历；
- 项目经历；
- 技能与工具；
- 证书、奖项和作品；
- 用户在材料中明确写出的地点、岗位等求职约束。

禁止自动形成：

- 性格、心理、道德或疾病标签；
- 没有文本证据的能力判断；
- 将团队成果自动归为个人成果；
- 将针对某个岗位的包装表述自动提升为长期偏好；
- 从姓名、学校或经历推断敏感属性。

每个 Claim 必须包含至少一个证据切片。用户确认页显示字段、值、来源文件、版本和原文定位。用户可以接受、编辑或拒绝；编辑会保留原始候选和用户修改记录。

多个文件冲突时，系统保留两项来源并标记 `conflict`，不自动选择最新文件为真。用户确认后，旧 Fact 变为 `superseded`，不会物理覆盖历史。

## 8. API 合约

所有 `/v1/me/*` 接口要求 Supabase Bearer JWT。

```text
POST   /v1/me/documents
GET    /v1/me/documents
GET    /v1/me/documents/{document_id}
GET    /v1/me/documents/{document_id}/versions
DELETE /v1/me/documents/{document_id}

GET    /v1/me/profile
GET    /v1/me/profile/claims
PATCH  /v1/me/profile/claims/{claim_id}
```

`POST /v1/me/documents` 使用 multipart：

- `file`：必填；
- `kind`：必填；
- `title`：可选；
- `replace_document_id`：上传新版本时可选。

成功返回 `202 Accepted`，包含 `document_id`、`version_id`、`status` 和可轮询的状态 URL。重复请求通过 `user_id + sha256 + kind` 幂等。

现有 `/v1/chat` 改为从鉴权上下文获取 `user_id`。迁移期间可以保留请求体字段但不得用于授权，随后从公开 Schema 删除。

## 9. Agent 集成

新增两个只读接口：

```python
class ProfileStore(Protocol):
    async def get_context(self, user_id: str, purpose: str) -> ProfileContext: ...

class PrivateCorpusStore(Protocol):
    async def search(
        self, user_id: str, query: str, document_ids: tuple[str, ...], limit: int
    ) -> tuple[PrivateDocumentHit, ...]: ...
```

Context Router 根据任务选择上下文：

- 日常情绪陪伴：默认不检索简历全文；
- 岗位匹配：读取确认档案，并检索与岗位要求相关的证据；
- 简历修改：限定到用户选择的简历版本；
- 个人陈述或面试准备：检索相关经历和能力证据；
- 用户询问文件内容：限定到明确文件或当前主版本。

Context Compiler 的装配顺序：

```text
Policy / Skill
+ Working Context
+ MemOS Personal Memory
+ Confirmed Structured Profile
+ Private Corpus Evidence
+ Shared RAG Evidence
+ Tool / Product State
→ Model
```

私有文档命中属于不可信数据，不能携带系统指令。回答引用 `document_id + version + page/section`。未确认 Claim 不进入默认 Agent 上下文；只有在“请帮我检查提取结果”等审核任务中使用。

## 10. 删除、替换与一致性

删除采用异步传播：

```text
标记 deleting
→ 立即停止检索和下载
→ 删除 Storage 对象
→ 删除切片和向量
→ 拒绝/删除未确认 Claims
→ 将仅由该文件支持的 Facts 标记 disputed
→ 清理缓存
→ 标记 deleted
```

已由用户确认且仍有其他来源支持的 Fact 可以保留；只有被删除文件单独支持的 Fact 不得继续作为确定事实。删除任务可重试并保留最小审计记录。

替换文件会创建新版本，不修改旧版本内容。新版本完成解析和索引后才原子切换 `current_version_id`；失败时旧版本仍可用。

## 11. 安全和隐私

- Supabase Auth JWT 是用户身份唯一来源；
- RLS、服务层和检索查询三层校验用户作用域；
- Storage Bucket 保持私有；
- 日志不保存原始文件、完整切片、Embedding、档案值或签名 URL；
- 文件名在展示前转义，存储路径使用系统生成 ID；
- 文档内容一律视为不可信输入，防止提示注入；
- 用户可以看到系统从文件中提取了什么以及引用来源；
- 删除操作返回任务回执，完成后验证所有检索路径不再命中；
- Supabase service role key 仅在后端和 Worker 环境中使用。

## 12. 错误处理和降级

- Storage 不可用：上传失败，不创建可见文档；补偿任务清理 pending 行；
- Parser 失败：保留文件并显示失败原因，允许重试或删除；
- Embedding 不可用：保留解析文本和全文检索，状态显示降级；
- 档案提取失败：私有文档仍可检索，允许单独重试提取；
- Supabase 不可用：Agent 不伪造个人资料，只使用 MemOS 和当前会话并返回内部降级状态；
- 引用来源已删除或版本失效：不向模型提供该命中。

## 13. 测试与验收

单元测试：

- PDF、DOCX、TXT 解析和位置保留；
- 文件签名、大小、重复和非法文件校验；
- 分块和结构化 Claim Schema；
- Claim 接受、编辑、拒绝和冲突处理；
- Context Router 不在无关对话中加载简历。

集成测试：

- 上传到 ready 的完整状态流；
- Supabase Storage、PostgreSQL、pgvector 写入；
- 用户 A 无法列出、下载、搜索、修改或删除用户 B 的数据；
- JWT 中的用户身份覆盖并拒绝请求体伪造标识；
- 文件删除后 Storage、全文搜索、向量搜索和 Agent 均无法命中；
- 替换失败时旧版本保持可用；
- Embedding 或提取失败时按设计降级。

Agent 验收场景：

- “根据我的简历分析这个岗位”同时引用岗位来源和简历页码；
- 未确认 Claim 不被描述为用户事实；
- 用户纠正教育或经历后旧值不再正常进入上下文；
- 日常倾听对话不会无故检索或暴露简历内容；
- 回答无法找到个人证据时明确说明资料不足。

## 14. 非目标

第一版不包括：

- 图片或扫描版简历 OCR；
- 在线协同编辑器；
- 自动代投简历；
- 将全部用户资料同步到 MemOS；
- 支持任意办公文件格式；
- 从第三方网盘或邮箱自动读取私人文件；
- 基于未确认资料自动修改职业方向。

## 15. 实施切分

本设计作为一个功能域，但实施应分为依赖明确的阶段：

1. Supabase 配置、Auth Principal、Schema、RLS 和 Storage；
2. 上传 API、版本、状态和删除；
3. Worker、解析、切片和私有索引；
4. Claims 提取、审核和 Structured Profile；
5. Context Router、Agent 私有检索和引用；
6. 跨用户安全、删除传播、故障降级和端到端验收。
