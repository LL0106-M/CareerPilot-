# CareerPilot RAG MVP 设计

> 本文只定义第一版知识库：知识从哪里来、如何转成统一文档、如何切分与索引。Personal Memory 继续由 MemOS 管理，不进入本知识库。

## 1. MVP 结论

CareerPilot 建立**一个逻辑知识库、三个内容分区**：

1. `ai_frontier`：前沿 AI、Agent、RAG、Memory、Harness 等专业信息；
2. `job_opportunity`：岗位、招聘公告、宣讲会与报名信息；
3. `curated_document`：开发者在后台上传并审核的政策、职业路径、学习资料和陪伴方法。

知识库只有两个入口：

```text
检索 Skill 产出的 Markdown ─┐
                             ├→ 暂存 → 清洗/去重/版本化 → 切分 → 索引 → 发布
开发者后台上传的文件 ────────┘
```

Skill 结果不是 Memory。它是外部知识候选；用户偏好、经历、目标与陪伴关系仍进入 MemOS。

## 2. 两个 Skill 的选择

### 2.1 前沿 AI 检索：`ai-radar`

候选来源：[LearnPrompt/ai-news-radar](https://github.com/LearnPrompt/ai-news-radar)

选择原因：

- 面向 AI 模型发布、Agent、研究、产品和行业动态；
- 公开静态 JSON，约 30 分钟更新，无需 API Key；
- 每条信息保留原文链接和数据时间；
- 只读，适合先作为采集源，不给 Agent 外部写权限。

限制：它更像 AI 资讯雷达，不覆盖所有论文与技术文档。因此，当用户问具体技术问题时，后续可以增加官方文档/论文补充检索，但 MVP 不再引入第三个 Skill。

### 2.2 岗位检索：`web-search`

候选来源：[ogulcancelik/agent-skills 的 web-search](https://github.com/ogulcancelik/agent-skills/blob/main/skills/web-search/SKILL.md)

选择原因：

- 能先搜索，再打开结果页并抽取 Markdown；
- 不绑定印度、欧美 ATS 或单一招聘平台；
- 可通过查询模板覆盖国内政府公告、高校就业网、国央企招聘官网和招聘平台；
- 适合作为“发现 URL + 抓取正文”的底座，CareerPilot 自己负责岗位分类。

运行要求与风险：需要 Node.js、Bun、本地 Chromium 和网络访问；可能遇到反爬、登录墙与站点条款限制。MVP 只抓公开页面，不绕过登录、验证码或访问限制。

### 2.3 为什么不直接采用现成求职 Skill

现有专用 Skill 多面向印度招聘站或 Greenhouse/Ashby/Lever，和 CareerPilot 需要的公务员、选调、事业单位、国央企及国内校招来源差异较大。第一版复用通用搜索 Skill，并在 CareerPilot 中维护来源模板，比改造一个地区错配的全流程求职 Skill 更小。

## 3. Skill 到知识库的交付契约

两个 Skill 都必须输出同一种 Markdown 文档。每条 AI 信息或每个岗位单独一份，不允许把十条结果拼成一个大文档。

```markdown
---
document_id: sha256(canonical_url + content_hash)
content_type: ai_frontier | job_opportunity
source_type: skill_ai_radar | skill_job_search
title: "..."
canonical_url: "https://..."
source_name: "..."
source_tier: 1 | 2 | 3 | 4
published_at: "2026-10-20T08:00:00Z" # 未知则 null
fetched_at: "2026-10-20T09:00:00Z"
valid_until: null
language: zh-CN
region: []
organization: null
job_family: []
content_hash: "sha256:..."
---

# 标题

## 摘要

只写原文可支持的摘要，不补造事实。

## 正文

清洗后的正文或招聘公告内容。

## 结构化要点

- 对 AI：发布方、模型/项目、版本、关键变化、适用范围。
- 对岗位：单位、岗位、地点、对象、报名途径、截止日期、用工关系；原文未说明的字段写“未知”。

## 来源

- 原文：<canonical_url>
- 抓取时间：<fetched_at>
```

### 3.1 来源等级

| 等级 | 岗位信息 | AI 信息 |
|---|---|---|
| Tier 1 | 政府、高校就业中心、单位招聘官网 | 官方文档、官方博客、论文原文、项目仓库 |
| Tier 2 | 企业认证招聘页、官方认证账号 | 作者/研究机构公开说明、权威会议页面 |
| Tier 3 | 可回源的招聘或资讯聚合平台 | 可回源的专业媒体 |
| Tier 4 | 社区帖子、个人经验 | 社区讨论与个人解读 |

Tier 3/4 可以提供发现线索，但涉及报名截止、资格、模型能力等强事实时应回到 Tier 1/2。

## 4. 开发者后台上传

MVP 接受 `PDF / DOCX / Markdown / TXT / HTML`。上传时开发者必须填写：

- 标题与知识分区；
- 来源或版权说明；
- 适用地区/版本；
- 发布时间或版本时间（可为空）；
- 是否有失效日期；
- 审核状态。

文件先进入 `candidate`，解析成功且开发者预览确认后才进入 `active`。重新上传同一来源时创建新版本，不直接覆盖旧文档。

## 5. 摄取流水线

```text
Receive
→ Quarantine（candidate，不可召回）
→ Parse（转 Markdown，保留标题、表格、原页码）
→ Normalize（URL、日期、组织名、空白）
→ Validate（正文、来源、时效、恶意指令）
→ Deduplicate（canonical_url + content_hash）
→ Version（new / unchanged / superseded）
→ Chunk
→ Embed + Sparse Index
→ Publish active
```

搜索摘要不能直接入库；必须获取可回源正文。网页中的“忽略系统提示”等内容只当作不可信文本，不得改变 Agent 行为。

## 6. 切分策略

### 6.1 AI 前沿信息

- 一篇文章/一个发布事件是一个父文档；
- 低于约 1,200 个中文字符时保持单块；
- 长文按 Markdown 标题切分，目标 600–900 字，重叠 80–120 字；
- 代码块、表格和一个完整结论不从中间截断；
- 每个 chunk 继承标题、原文 URL、发布时间、技术主题和版本。

### 6.2 岗位信息

- 一个岗位或一份招聘公告是一个父文档，绝不跨岗位混切；
- 短公告整体作为一个 chunk；
- 长公告按“单位与岗位 / 职责 / 任职条件 / 流程与时间 / 用工关系”切分；
- 每个 chunk 重复携带单位、岗位、地点、截止日期和来源 URL；
- 截止日期和用工关系只抽取原文明示内容，未说明则保持 `unknown`。

### 6.3 开发者上传文档

- 优先按标题层级和段落语义切分，目标 800–1,200 字，重叠约 100 字；
- 表格整体保留，并额外生成一段可检索的表格说明；
- PDF chunk 保留页码；政策/指南保留章节路径与适用版本；
- 不同文档、不同版本不混在同一 chunk。

这些数值是 MVP 初值，需要通过真实查询集评估后调整，不作为永久规则。

## 7. 索引设计

第一版采用混合检索：

```text
Metadata Filter
→ Dense Vector Search
+ Sparse/BM25 Search
→ Rerank
→ Top chunks + parent metadata + citations
```

- 逻辑知识库统一，物理上按 `ai_frontier / job_opportunity / curated_document` 分区；
- 使用 `content_type`、地区、岗位族、发布时间、有效期、来源等级和版本做过滤；
- 向量索引初选开源多语言 Embedding；关键词索引用 PostgreSQL 全文检索，现有架构继续采用 PostgreSQL + pgvector；
- 排序同时考虑语义相关性、关键词命中、来源等级、发布时间和是否过期；
- 岗位硬过期后退出默认召回但保留审计；AI 旧版本标记 `superseded`，需要历史问题时仍可检索。

## 8. Agent 查询闭环

```text
用户目标
→ 判断查询 AI 知识 / 岗位 / 开发者资料
→ 检索现有知识库
→ 足够：带引用回答
→ 不足或过期：调用对应 Skill
→ Skill 返回 Markdown 候选
→ 本轮先作为 Tool Evidence 回答
→ 通过摄取质量门后发布进知识库
→ 下次查询直接复用
```

首版“Agentic”的关键不是让模型随意抓网页，而是：模型可以发现知识缺口并选择 Skill；确定性代码负责来源、去重、版本、过期和发布。

## 9. MVP 边界与验收

### 本期包含

- 两个 Skill 的接入契约；
- Skill 结果转标准 Markdown；
- 开发者后台文件上传入口；
- candidate/active/superseded 状态；
- 三类切分策略；
- 混合检索、元数据过滤、引用返回；
- 知识不足时调用 Skill，再将合格内容入库。

### 本期不包含

- 自动投递岗位；
- 绕过招聘网站登录或反爬；
- 把浏览/收藏直接推断为用户偏好；
- 将外部文档写入 MemOS；
- 全网无目标持续爬取；
- 第一版即实现知识图谱或 GraphRAG。

### 核心验收

1. AI 与岗位 Skill 均能生成符合契约的单条 Markdown；
2. 同一 URL 内容未变化时不产生重复 active 版本；
3. 岗位检索不会把不同岗位切进同一 chunk；
4. 过期岗位不出现在默认结果；
5. 回答中的关键事实能回到原文 URL 与 chunk；
6. MemOS 中不存在 Skill 抓取的外部正文。

## 10. 已实现的精简 Agentic RAG（v0.2）

### 10.1 统一证据与物理索引

MVP 不再为 Passage、三元组、BM25、表格事实分别部署服务。它们统一写入 SQLite
`evidence_units`：每条记录同时保留 `embedding_text`、FTS 文本、类型、父级、来源、领域与
结构化字段。物理上只有原始来源文件和一个证据数据库；LightRAG 式关系导航复用带来源的
三元组字段，不引入 Neo4j/Milvus。

StructGPT 式线性化包括：

```text
[KG_TRIPLE] AI产品经理 | 需要 | 理解大模型能力边界
[TABLE_ROW table=jobs row=job-032] (职位, AI产品经理) | (城市, 上海)
[ROW_FACT table=jobs] job-032 | 城市 | 上海
[PASSAGE heading=任职要求] ……原文……
```

结构化 payload 仍保留用于过滤和计算；线性化文本用于 Sparse、Dense 和模型阅读。

### 10.2 查询与混合检索

查询计划不再用岗位/AI关键词表猜测领域。Agent 或上游 Planner 显式提供 `domain`、
`sub_queries`、`requires_freshness` 与 `validation_target`。每个问题默认执行 Sparse 和可选
Dense；同时在 `kg_triple` 上执行整句 Query-to-Triple。最强种子做一次带来源的一跳扩展，
避免无限图遍历。

多路结果先用 RRF 融合，再按来源等级、直接/桥接角色和通道支持数重排。MVP 不部署独立
Cross-Encoder；只有离线评估证明当前重排不足时再增加。

### 10.3 Clues 与停止

检索结果形成带 `evidence_id + source_uri + role` 的 Clues。默认最多两轮：证据充分则
`enough`；无结果或需要时效核验则 `needs_online_search`；第二轮没有新 Evidence Unit 则
`no_new_evidence`；达到上限则 `max_depth`。Clues 保存可引用事实，不保存模型隐式思维链。

### 10.4 模型成本

- 探索/查询改写温度固定为 `0.4`；
- 证据规划与判断温度固定为 `0.0`；
- Embedding 通过 OpenAI-compatible 接口可选启用，默认不下载模型；
- Embedding 服务失败时自动降级到 Sparse + 图关系；
- 第一版不引入 Neo4j、Milvus、独立 Cross-Encoder 或无目标全网爬取。

### 10.5 周期网页来源

搜索 Skill 负责发现 URL，Fetch Connector 负责抓正文。RAG 内部只维护轻量
`source_registry`：URL、来源类型、知识域、刷新间隔、最近抓取时间与 content hash。
岗位可配置 6—24 小时，官方技术资料可配置一周；只有到期来源进入抓取队列，未变化页面
不重复切分和索引。
