# CareerPilot 轻量岗位情报摄取设计

## 目标

把外部岗位搜索结果稳定地转成 CareerPilot RAG 可检索、可核验、可增量更新的
Evidence，而不部署完整 Mage 服务。

## 设计取舍

- 复用 `ocr-skill-master` 的来源分级、岗位核验和结构化思想，改造成
  `career-job-intelligence` Skill；不复用其与 CareerPilot 无关的简历和面试模块。
- 复用 Mage 的 Source → Transform → Validate → Load 流水线分层思想，不复制 Mage
  的调度服务、Web UI、数据库和 Pro RAG 组件。
- 搜索与网页抓取由外部 Search/Fetch Tool 完成。本模块只接收 JSON 岗位记录，避免将
  不稳定的站点适配逻辑耦合进 RAG。
- 每条岗位以稳定身份 ID 入库；内容哈希未变化时跳过重建索引，发生变化时覆盖同一文档。
- 官方来源与线索来源分开标注。线索可以进入候选证据，但不能伪装成已核验事实。

## 数据流

```text
Search/Fetch Tool
  -> JobRecord JSON
  -> normalize（URL、公司、城市、岗位类别、招聘渠道）
  -> validate（必填字段、来源等级、状态、日期）
  -> deduplicate（稳定岗位身份 + 内容哈希）
  -> SourceDocument（Markdown 正文 + table_rows 元数据）
  -> RagIndexer
  -> Passage + Table Row/Fact Evidence
  -> source_registry 更新抓取时间和内容哈希
```

## 失败与边界

- 缺少公司、岗位名称或来源 URL 的记录拒绝入库，并计入 `rejected`。
- 同批次重复岗位只处理一次。
- 相同来源、相同内容哈希计入 `unchanged`，不重复生成向量。
- 不自动猜测截止时间、编制、招聘状态或来源等级。
- MVP 不运行定时调度器；现有 `due_sources()` 作为之后的 scheduler 接口。

## 开源复用

- 岗位 Skill 基于 `lgd_sunday/ocr-skill`（MIT）的方法与 Schema 进行修改。
- Mage AI（Apache-2.0）仅作为流水线架构参考；本实现不复制或依赖 Mage 源码。

