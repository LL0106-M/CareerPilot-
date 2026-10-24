# CareerPilot RAG MVP 设计

> 当前版本：v0.3，上线导向基线。本文定义 RAG 的知识来源、访问边界、数据加载生命周期和生产部署边界。Personal Memory 继续由记忆系统管理，不进入 RAG 知识库。

## 1. 系统边界

CareerPilot RAG 只处理三类知识来源：

| Scope | 中文名称 | 数据来源 | 默认处理方式 |
|---|---|---|---|
| `jobs` | 岗位信息 | 公开招聘来源的在线查询 | 实时搜索并返回结构化结果，不默认进入长期向量索引 |
| `preparation` | 面试准备知识 | 开发者或管理员后台上传；必要时在线补充 | 后台资料审核后建立长期索引；在线资料仅作为本轮证据，审核后才可入库 |
| `personal` | 私人资料 | 当前用户上传的简历、JD、作品集和笔记 | 按 `owner_user_id` 建立私有索引，只允许当前用户检索 |

以下信息不属于 RAG：

- 用户的长期目标、稳定偏好、个人约束和陪伴关系属于 Memory；
- 当前轮收集到的岗位倾向属于会话状态，用户确认长期保存后才进入 Memory；
- Agent 的任务状态、工具调用和错误恢复属于 Runtime/Harness；
- 岗位收藏、申请进度和任务清单属于产品业务数据，不作为公共知识文档。

## 2. 三类知识源

### 2.1 岗位信息：在线搜索

岗位信息具有强时效性，MVP 不再把岗位网页作为长期公共知识库的主要分区。岗位链路为：

```text
用户表达岗位倾向
→ Intent Router 识别 job_discovery / job_search
→ Slot Manager 收集岗位、地点、经验阶段、企业类型等条件
→ 条件不足：继续询问
→ 条件足够：生成结构化 JobSearchRequest
→ 在线搜索或招聘数据源查询
→ 标准化、去重、时效校验、排序
→ 返回本轮岗位证据
```

最小搜索槽位：

- `role`：产品、开发、算法、运营等；
- `location`：城市、地区或不限；
- `experience_level`：实习、校招、初级或社招。

重要但可后续补充的槽位：

- `organization_type`：国企、央企、事业单位、大厂、外企、创业公司等；
- `industry`、`salary_range`、`education`、`work_mode`；
- 是否接受异地、出差、加班和特定用工关系。

岗位搜索结果必须尽量标准化为：

```json
{
  "job_id": "source-and-content-hash",
  "title": "AI 产品经理",
  "company": "示例公司",
  "location": "北京",
  "organization_type": "央企",
  "salary": null,
  "experience_level": "校招",
  "requirements": [],
  "source_url": "https://example.com/job/1",
  "published_at": null,
  "retrieved_at": "2026-10-22T10:00:00+08:00",
  "expires_at": null
}
```

搜索结果可以进入短期缓存。只有用户收藏、加入申请流程或明确要求保存时，才生成岗位快照；岗位快照属于该用户的业务数据或私人资料，不转化为公共面试知识。

岗位网页需要经过结构化信息抽取，但不进入 GraphRAG。抽取目标至少包括：

- `company_name`：企业或组织名称；
- `organization_type`：央企、地方国企、政府、事业单位、民企、外企等；
- `role_title`：来源页面中的岗位名称；
- `role_family`：产品、开发、算法、运营等归一化岗位类型；
- `recruiting_type`：实习、校招、社招等；
- `employment_type`：编制、企业合同、劳务派遣、实习等；
- `locations`、`deadline`、`posted_at`、`apply_url`；
- `job_description` 与 `requirements`；
- `source_url`、`source_level`、`verified_at` 和状态。

岗位抽取采用“规则优先、模型补充、字段级校验”的流程：

```text
搜索结果或招聘正文
→ DOM / JSON-LD / 表格等确定性字段抽取
→ LLM 对非结构化正文补充候选字段
→ 日期、企业类型和岗位族归一化
→ 字段级来源片段与置信度校验
→ 无法确认的字段保留 unknown
→ 生成 JobRecord
```

模型不得根据企业名称主观猜测企业性质，也不得根据抓取日期臆造投递截止时间。每个关键字段应保存 `source_text / extraction_method / confidence`，便于前端展示来源和后台纠错。

### 2.2 面试准备知识：开发端知识库 + 在线补充

长期面试知识由开发者或管理员维护，不接受普通用户直接写入公共知识库。内容包括：

- 面试题库与参考要点；
- 岗位能力模型与行业知识；
- 面试方法论、案例分析和表达框架；
- 经过授权和审核的面经；
- 产品后台认可的政策、职业路径和学习资料。

面试准备知识同时支持前端独立资源页，但前端资源与后台专业知识库必须分开。前端只展示与岗位关联的“面经/往年题”和“学习资料”，不直接展示后台上传的内部知识文档、Parent/Child、Embedding 或 Triple。

前端资源只保留两种简单类型：

- `interview_experience`：该企业、该岗位或该岗位族相关的面经与往年题；
- `learning_material`：该岗位或岗位族相关的学习资料。

资源优先关联具体 `job_id`。无法定位到具体岗位时，关联 `company_name + role_family`；通用学习资料可以只关联 `role_family`。不为每道题建立复杂的题型、难度、面试轮次和能力标签体系。

资源来源和可见性固定为：

| origin | 形态 | 前端可见性 | RAG 处理 |
|---|---|---|---|
| `user_upload` | 用户上传 PDF / Word 附件 | 仅上传用户可见 | 作为用户私有附件做父子分块，不进入公共图谱 |
| `web_link` | 在线搜索得到的原始链接 | 可展示标题、简述和原链接 | 默认不复制为平台公开正文；需要回答时可临时读取 |
| `backend_internal` | 开发端上传的专业知识 | 前端不展示 | 进入公共专业知识索引，可生成 GraphRAG |

最小资源模型只需要：

```text
resource_id
resource_type: interview_experience | learning_material
origin: user_upload | web_link | backend_internal
visibility: private_owner | public_link | internal
job_id?
company_name?
role_family?
title
file_object_id? | source_url?
owner_user_id?
created_at / retrieved_at
```

用户上传的附件默认是私有数据，不因出现在“面经”页面就变成其他用户可见内容。在线资源在前端直接附原链接；只有开发端另行审核并作为 `backend_internal` 发布时，正文才进入长期公共索引。

GraphRAG 只构建在 `preparation + backend_internal` 的专业知识语料上。用户附件和临时网页链接不进入公共知识图谱，避免隐私泄漏、版权复制和低质量关系污染。

默认先检索开发端知识库。出现以下情况时才允许在线补充：

- 本地没有相关证据；
- 本地证据来源不足；
- 用户明确要求最新信息；
- 问题包含近期政策、企业动态或技术变化。

在线搜索摘要不能直接进入长期公共索引。前端资源页只保存标题、简述、原链接和关联岗位；需要回答时可临时读取原页。若开发端希望将其沉淀为内部专业知识，必须另行抓取原文、验证来源和版权，并以 `backend_internal` 审核发布。

### 2.3 私人资料：用户隔离索引

私人资料包括：

- 简历与简历版本；
- 用户针对某岗位上传的 JD；
- 作品集、项目材料和个人陈述；
- 用户自己的面试笔记和求职材料。

每个私人文档必须携带 `owner_user_id`。检索过滤必须在数据库查询阶段执行，不能先全库召回再在应用层过滤。`personal` 单独查询时不允许自动降级到互联网搜索，也不能访问其他用户的数据。

用户删除私人文档时，需要同时删除或失效：

- 原始对象文件；
- 文档版本和解析产物；
- chunks、向量和全文索引；
- 与该文档直接关联的缓存。

## 3. 路由和查询职责

```text
Context Engine
决定允许访问 jobs / preparation / personal 中的哪些来源
        ↓
RAG Query Planner
针对已授权来源拆解和改写查询，但不得扩大来源权限
        ↓
Job Search / Preparation Retriever / Personal Retriever
        ↓
统一 Evidence Bundle
        ↓
模型基于证据回答并提供引用
```

例如用户说“结合我的简历看看北京央企有哪些 AI 产品岗位，并告诉我怎么准备”：

```json
{
  "sources": ["jobs", "preparation", "personal"],
  "job_filters": {
    "role": ["AI 产品经理", "技术产品经理"],
    "location": ["北京"],
    "organization_type": ["央企"]
  },
  "requires_freshness": true
}
```

Query Planner 可以为三个来源生成不同查询，但不能擅自添加未授权来源。

## 4. 数据加载总览

三类知识源不共用同一条加载链路：

```text
岗位信息
在线查询 → 标准化 → 去重 → 时效校验 → 短期缓存 → 返回

面试准备知识
开发端上传 → 对象存储 → candidate → 异步解析 → 校验 → 切块
→ Sparse + Dense 索引 → 审核预览 → 原子发布 active

私人资料
用户上传 → 鉴权与配额 → 私有对象存储 → 异步解析 → 切块
→ 带 owner_user_id 的 Sparse + Dense 索引 → ready
```

所有异步加载任务必须具有可查询状态：

```text
uploaded → queued → parsing → indexing → ready
                         └→ failed
```

面试准备知识额外具有发布状态：

```text
candidate → active → superseded / archived
```

## 5. 开发端知识加载

### 5.1 上传契约

开发端上传文档时至少填写：

- 标题、知识主题和适用岗位；
- 来源、授权或版权说明；
- 地区、语言和适用版本；
- 发布时间、审核人和可选失效日期；
- 文件内容哈希。

MVP 优先支持 `PDF` 和 `Markdown`。`DOCX / TXT / HTML` 在对应解析器完成并通过测试后再开放，不在接口层虚假声明支持。

### 5.2 加载流水线

```text
Receive
→ Store Original Object
→ Quarantine（candidate，不可召回）
→ Parse（正文、标题、页码和表格）
→ Normalize（日期、URL、组织名和空白）
→ Validate（格式、来源、权限、时效和提示注入文本）
→ Deduplicate（content_hash + source_uri）
→ Version（new / unchanged / superseded）
→ Chunk
→ Sparse Index + Dense Embedding
→ Preview and Review
→ Atomic Publish active
```

发布必须是原子操作：新版本全部索引成功后才切换为 `active`；失败时旧版本继续提供服务。

### 5.3 父子分块原则

所有进入长期索引的文档型知识统一采用 Parent–Child Chunking。子块负责精准召回，父块负责向模型提供完整语境；检索命中子块后，默认根据 `parent_id` 取回对应父块，再进行上下文裁剪和引用。

```text
Canonical Document
→ 按标题、章节、页码和语义边界生成 Parent Chunk
→ 在 Parent 内按段落、问题、经历或知识点生成 Child Chunk
→ Child 建立 Sparse + Dense 索引
→ Parent 保存完整上下文并可建立辅助索引
→ Child 命中后回取 Parent
```

父块初始目标为 1,000–1,800 tokens，子块初始目标为 300–700 tokens。长度使用当前 Embedding 模型对应的 tokenizer 计算，不再把固定字符数作为生产标准。只有连续长文本的子块之间使用 50–100 tokens 重叠；标题边界、面试题、简历项目和表格行之间不机械重叠。

语义完整性规则：

- 一道面试题、回答框架、示例和注意事项归属同一父块；子块可以分别表示问题、框架和示例，但都指向该父块；
- 一段工作经历或项目经历作为一个父块，背景、职责、行动、结果可以成为子块；
- JD 的职责、任职要求、优先条件分别形成子块，并共同指向该 JD 父块；
- 表格整体作为父证据，表格行和行事实作为子证据，禁止按字符截断表格；
- 每个父块和子块都继承文档版本、来源、页码、标题路径、主题、适用岗位和权限信息；
- Graph Triple 必须绑定产生它的 `child_id`，并可沿 `parent_id` 回到完整原文。

父子关系至少包含：

```json
{
  "chunk_id": "child-123",
  "parent_id": "parent-45",
  "document_id": "doc-9",
  "chunk_level": "child",
  "heading_path": ["产品经理面试", "需求分析"],
  "page_start": 3,
  "page_end": 4
}
```

父子分块适用于 `preparation` 和 `personal` 文档，也适用于较长的官方招聘公告。普通岗位搜索结果保持一个 `JobRecord` 对应一个 `API_OBJECT` Evidence，不为了形式统一强行拆成父子块。

### 5.4 表格四级向量化与图片边界

表格不沿用文本父子切块，而是保留完整表格结构并建立四级检索表示：

| 层级 | Evidence | 内容 |
|---|---|---|
| L1 | `TABLE` | 表名、用途、标题、列名集合和表格摘要 |
| L2 | `TABLE_COLUMN` | 列名、列语义、数据类型和代表值 |
| L3 | `TABLE_ROW` | 行标识以及该行全部字段值 |
| L4 | `TABLE_FACT` | `行实体 | 列名 | 单元格值` 的原子事实 |

四级表示都可建立 Sparse 与 Dense 索引，但必须共享 `table_id`，并通过 `column_id / row_id / cell_id` 保持层级关系。空单元格、纯序号和无语义重复值不生成 L4 向量，防止索引无效膨胀。召回低层事实后，可以沿层级回取对应行和完整表格上下文。

图片不进行文本式切块。解析阶段只登记 `ImageAsset`，至少保存 `image_id`、`document_id`、页码、对象存储地址、图片类型、边界框和可选说明。图片中的 OCR 文本或人工说明归属所在页面的文本 Parent，不把一张图片机械拆成多个向量块；后续若需要多模态检索，再为完整图片增加独立的视觉向量。

### 5.5 GraphRAG 生成时点

GraphRAG 只应用于 `preparation + backend_internal` 专业知识，不应用于 `jobs`、`personal`、用户附件或临时网页链接。它在内部专业知识完成文本父子分块后执行，是索引阶段的旁路产物：

```text
Canonical Document
→ Parent–Child Chunking
→ 每个 Child 建立 Passage Node
→ 从 Child 一次抽取 Phrase / Relation / Triple
→ Phrase 归一化并建立 Phrase Embedding
→ Passage --contains--> Phrase
→ Phrase --relation--> Phrase
→ Embedding Top-K + 阈值生成 Phrase --synonym--> Phrase
→ Triple 与 Passage 分别建立 Dense + Sparse 检索表示
→ 所有节点和边绑定 source_child_id
```

Parent 不直接重复抽取关系，避免同一事实因父子重叠被写入两次。每条 Triple 必须携带 `document_id + source_child_id + source_uri + page`，图只负责关系导航；回答时仍沿 `source_child_id → parent_id` 回取原始文本。表格关系优先来自 L3/L4 的确定性结构，不使用模型重复猜测已有列值。图片在当前阶段不参与 GraphRAG。

第一版采用轻量 HippoRAG 2，不生成 Youtu-GraphRAG 的社区摘要和四层 Knowledge Tree。图中只保留 `passage` 与 `phrase` 两类节点，以及 `contains`、`relation`、`synonym` 三类边；Fact/Triple 作为可检索证据及 relation edge 的来源，不重复成为必须遍历的图节点。SQLite 原型允许对新增 Phrase 与现有 Phrase 做受限 Top-K 相似度比较；生产环境必须用 pgvector ANN 生成同义候选，禁止全库两两比较。

离线图索引发布需要同时检查：

- 专业知识的每个 Child 都存在对应 Passage Node；
- 每个 Triple 的主体和客体都存在 Phrase Node；
- 每个 Triple 都有 relation edge 和原文 Evidence；
- Passage 与该段抽取出的 Phrase 之间存在 contains edge；
- `graph_node_sources` 和 `graph_edge_sources` 可以回到 `document_id + child_id + evidence_id`；
- 删除或替换文档后，无来源节点和边被清理，共享 Phrase 不被误删。

### 5.6 HippoRAG 2 风格在线图查询

图查询只在专业知识域且问题需要概念关联、跨段落或多跳证据时启用。第一版不让 LLM 逐步浏览全图，使用有界的检索与 PPR：

```text
Query
├─ Passage Sparse / Dense Retrieval
└─ Triple Sparse / Dense Retrieval
          ↓
Passage Seeds + Phrase Seeds
          ↓
Recognition Filter（第二阶段可选）
          ↓
Personalized PageRank（固定迭代次数）
          ↓
仅保留 Passage Node 并按 PPR 排序
          ↓
与原始 Sparse / Dense 结果做 RRF
          ↓
Child 命中 → Parent 上下文回取 → 引用输出
```

简单事实问题仍可由 Sparse / Dense 直接完成，图结果只是额外召回通道。PPR 必须设置候选域、迭代次数和返回数量上限；任何 Phrase、Triple 或图路径都不能直接作为无来源答案，最终回答证据必须落回 Passage 原文。

### 5.7 两级查询路由与 Agent 反馈协议

#### 5.7.1 成本优先的查询分析与图检索模式

所有需要外部证据的请求先进入 RAG Gateway，但不代表每次都访问本地知识库。查询分析层不调用 LLM，先输出标准化查询、意图、实体槽位、时效性、检索模式与图模式；只有真正进入本地语义检索时才生成 Query Embedding。

检索模式：

- `web_only`：最新岗位、明确联网搜索等问题，跳过本地稀疏、稠密和图检索；
- `local_only`：用户私人资料，只在 owner 隔离后的本地索引中检索；
- `local_first`：稳定专业知识先查本地，证据不足再联网；
- `web_first`：强时效专业问题先联网，联网无结果才降级本地；
- `hybrid`：岗位与私人资料匹配等跨知识域任务，并行获取各域证据。

图检索模式：

- `none`：定义、直接事实等问题不使用图；
- `local`：Query-to-Triple 后在种子周围最多两跳、最多 500 个节点的子图执行 PPR；
- `global`：宏观体系、共性和趋势问题在指定专业知识域的完整图上执行 PPR；
- `hierarchical`：先全域定位 Passage，再以原始 Triple 与全局 Passage 为种子进行局部下钻。

查询向量在单次请求和短期进程缓存中复用，同一个标准化查询不会为 Passage、Triple 和不同知识域重复调用 Embedding 服务。Query-to-Triple 的稀疏和稠密候选先使用 RRF 做低成本 Recognition Filter，默认只保留最多 5 个图种子；后续可在模糊候选上增加可选 LLM Filter，而不是每次调用模型。

PPR 使用 Phrase seed 与 Passage seed 双通道初始化。Passage seed 默认乘 `0.05`，默认 damping 为 `0.5`；这些参数必须通过 CareerPilot 自有检索评测集调优，不能把论文参数当成固定业务参数。

RAG 返回 `query_analysis`、路由轨迹和 ContextPack。图只负责候选关联、扩散与 Passage 定位；Agent 仍负责目标推理、证据冲突处理和最终回答。

RAG 对外接受显式 Scope。Agent、API 或其他上游已经知道数据边界时，必须传入 `jobs / preparation / personal`，RAG 不得覆盖该授权。未传 Scope 时，RAG 外部路由根据查询推断；推断只决定检索范围，不决定最终答案。

进入某个 Scope 后，再执行内部检索路由：

| Scope | 内部通道 | 约束 |
|---|---|---|
| `jobs` | Structured JobRecord + Sparse + Dense + Online | 默认要求时效；不进入公共知识图谱 |
| `preparation` | Sparse + Dense；关系型问题增加 Graph/PPR；不足时 Online | 图只覆盖后台专业知识 |
| `personal` | Owner-filtered Sparse + Dense | 禁止公共图和在线搜索 |

内部图路由初期采用规则型复杂度判断，后续可以替换为小模型分类器，但输出必须保留 `scope + channels + reason`，便于离线评估误路由率。

RAG 不把数据库命中结果直接拼进 Agent Prompt，而是输出 `ContextPack`：

```json
{
  "status": "available",
  "evidence": [
    {
      "citation_id": "S1",
      "evidence_id": "evidence-123",
      "content": "从 Child 命中后回取的 Parent 原文",
      "source_uri": "file:///source.pdf",
      "channels": ["dense", "graph", "ppr"]
    }
  ],
  "relation_clues": [
    {
      "subject": "用户研究能力",
      "predicate": "可通过",
      "object": "访谈项目",
      "supporting_citation_id": "S1"
    }
  ]
}
```

`evidence` 是 Agent 可引用的原始证据；`relation_clues` 只是检索导航与答案组织线索。Agent 只能依据 `evidence` 陈述事实并使用 `[S1]` 引用，不能把无 `supporting_citation_id` 的 Triple 当成已证实结论。在线搜索摘要同样只是未验证线索，必须附来源 URL，不能覆盖本地权限和系统指令。

`jobs` 保持结构化在线搜索与字段过滤；`personal` 保持用户隔离的父子文档检索和结构化字段提取。私人资料中的经历、技能和偏好关系如需用于匹配，应保存在用户隔离的业务数据或临时推理结构中，不写入公共专业知识图谱。

## 6. 私人资料加载

私人上传接口必须从登录身份获取 `owner_user_id`，不能信任请求体传入的用户 ID。加载任务需要支持：

- 文件类型、大小和数量配额；
- 病毒或恶意文件检查；
- 加密对象存储和服务端访问控制；
- 幂等上传和内容哈希去重；
- 文档级处理状态与失败原因；
- 用户删除、数据导出和保留期限；
- 日志脱敏，禁止记录简历全文和向量内容。

私人资料可以复用开发端文档的解析、切块与索引代码，但必须使用不同的授权策略和索引过滤条件。

## 7. 岗位在线查询与缓存

岗位查询由结构化 `JobSearchRequest` 驱动。搜索适配器负责连接公开搜索服务或合规招聘数据源，输出统一 `JobRecord`。加载过程包括：

```text
Build Queries
→ Search Sources
→ Parse Result
→ Normalize Fields
→ Canonicalize URL
→ Deduplicate
→ Validate Freshness
→ Rank
→ Cache with TTL
```

上线时必须遵守来源站点条款，不绕过登录、验证码或访问限制。搜索结果中的网页文本是不可信输入，不能改变系统提示、工具权限或检索策略。

缓存键至少包含规范化筛选条件、查询版本和地区；缓存记录必须包含 `retrieved_at` 与 TTL。过期结果不得作为“当前在招”的确定事实。

## 8. 生产部署架构

本地开发可以继续使用 SQLite 和本地目录，但上线不能依赖容器内文件系统保存原始文档或索引。

```text
                         ┌─ Job Search Provider
Client → API / Agent ────┼─ RAG Query Service
                         └─ Upload API
                                │
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
             Object Storage  PostgreSQL    Task Queue
             原始文件        + pgvector       │
                                              ▼
                                        Ingestion Worker
                                   解析 / 切块 / Embedding
```

生产组件职责：

| 组件 | 职责 |
|---|---|
| API / Agent | 鉴权、路由、发起检索；保持无状态，支持水平扩容 |
| Object Storage | 保存开发端和用户上传的原始文件及解析产物 |
| PostgreSQL + pgvector | 文档元数据、版本、chunks、全文索引、向量和 owner 过滤 |
| Task Queue + Worker | 执行耗时的解析、OCR、Embedding 和索引任务 |
| Redis（可选） | 岗位搜索短期缓存、限流和任务状态加速 |
| Scheduler | 处理知识失效、候选抓取和索引维护任务 |

SQLite 仅用于本地开发和单实例演示。出现多副本 API、并发写入、后台 Worker 或正式用户数据后，应切换到 PostgreSQL + pgvector。

### 8.1 上线最低要求

- API 通过真实登录会话得到用户身份；
- 密钥由云平台 Secret 管理，不进入代码、镜像或前端；
- 数据库、对象存储和队列使用独立的生产资源；
- 上传和索引采用异步任务，API 不等待完整 Embedding；
- 数据库迁移可回滚，索引发布使用版本号或蓝绿切换；
- 健康检查区分 API、数据库、搜索服务和 Worker；
- 对在线搜索、Embedding 和模型调用设置超时、重试、熔断和费用上限；
- 对私人资料实施最小权限、删除闭环、备份加密和审计；
- 日志记录 document_id、job_id、trace_id 和耗时，不记录敏感正文。

## 9. 统一证据返回

三个 Retriever 最终返回统一 Evidence Bundle，便于融合、排序和引用：

```json
{
  "evidence_id": "evidence-123",
  "scope": "jobs",
  "kind": "job_record",
  "title": "AI 产品经理",
  "content": "……",
  "source_uri": "https://example.com/job/1",
  "published_at": null,
  "retrieved_at": "2026-10-22T10:00:00+08:00",
  "score": 0.87,
  "owner_user_id": null
}
```

`personal` 证据必须携带内部 owner 信息用于授权，但不得将 owner 标识暴露给模型回答或前端展示。

文档型证据还必须返回 `child_id`、`parent_id`、`document_id` 与页码。排序分数属于命中的子块；传给生成模型的正文默认使用父块或经过预算裁剪的父块，引用定位仍指向原始子块和页码。

## 10. 当前实现与目标基线的差距

当前代码已经具备 SQLite Evidence Unit、FTS5、Dense、RRF、轻量关系扩展和在线搜索回退，可继续作为本地原型。离线发布索引必须同时包含稀疏与稠密表示：每个可检索 Evidence Unit 写入一条 FTS5/BM25 记录和一条 Embedding 向量。Embedding 未配置、调用失败或向量数不匹配时，本次文档更新整体失败并保留旧索引；`--allow-sparse-only` 仅用于开发恢复，不能用于生产发布。在线查询阶段仍允许 Dense 服务短暂不可用时降级到 Sparse，但必须上报监控。

离线索引验收至少输出 `indexed_evidence`、`sparse_entries` 和 `dense_vectors`，正常发布应满足：

```text
indexed_evidence == sparse_entries == dense_vectors
```

下一阶段需要按本文基线调整：

1. `jobs` 从“本地知识域优先”调整为“槽位完整后执行在线结构化搜索”；
2. `preparation` 只允许开发端发布的公共知识，在线结果不能自动入库；
3. `personal` 移除对 `curated_document` 的兼容映射，只查询用户私有域；
4. 将上传、解析和索引从同步本地函数升级为可观测的异步任务；
5. 增加生产对象存储、PostgreSQL + pgvector、鉴权过滤和删除闭环；
6. 让 Context Engine 输出的来源授权直接约束 RAG，不再让模型二次扩大 scope。
7. 将现有单层字符分块升级为统一父子分块，并在存储层增加稳定的 `parent_id` 与 chunk level。

## 11. MVP 验收

1. 岗位倾向不完整时先追问，完整后才执行搜索；
2. 岗位结果包含来源、抓取时间和时效状态，过期缓存不会冒充当前岗位；
3. 普通用户不能向公共面试知识库发布内容；
4. 新版面试资料索引失败时，线上旧版本不受影响；
5. 私人资料在数据库检索阶段按登录用户过滤；
6. 删除私人资料后，原文件、chunks、向量和关联缓存完成删除或失效；
7. 在线内容不经审核不能进入长期公共索引；
8. 每条回答中的关键知识能够回到原始文档页码或在线 URL；
9. Memory 中不存在开发端知识正文或搜索抓取正文。
