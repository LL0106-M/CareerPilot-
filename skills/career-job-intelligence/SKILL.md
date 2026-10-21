---
name: career-job-intelligence
description: 搜索、核验并结构化当前招聘岗位，覆盖 AI/Agent 产品、互联网、国央企、公务员、选调和事业单位；在用户询问最新岗位、投递入口、截止时间或希望将岗位加入 CareerPilot RAG 时使用。
---

# Career Job Intelligence

把公开招聘网页转成可核验、可追溯的岗位记录。这个 Skill 管外部岗位知识，不保存用户的
个人偏好、投递经历或情绪；后者属于 Memory。

## 工作流程

1. 明确必要约束：岗位方向、招聘类型、地点与时间范围。缺少信息时只追问一个最影响结果的问题。
2. 搜索时先发现线索，再回到官方或近官方来源核验。涉及“现在、最新、还在招、截止时间”时必须重新联网。
3. 读取 [来源与分类规则](references/source-policy.md)，区分来源等级、单位性质、招聘渠道和用工/编制类型。
4. 每个岗位按 [岗位 Schema](references/job-record.schema.json) 输出 JSON。缺失事实使用 `null` 或 `unknown`，不得猜测。
5. 正式推荐只包含 S/A 级或明确解释过的 `unknown`；B/C 级单列为待核验线索。
6. 需要加入知识库时，将 JSON 数组交给项目的 `scripts/ingest_job_records.py`。不要把岗位事实写入用户 Memory。

## 搜索与核验要求

- 优先顺序：招录机关/公司官网 → 官方招聘站或公告 → 官方 ATS → 聚合平台线索 → 官方复核。
- 公务员、选调和事业单位以政府、组织、人社或招录专题网站为准。
- 国央企要分别记录 `organization_type` 和 `employment_type`；“央企岗位”不等于“有编制”。
- 记录原始岗位名称，不因匹配用户而改写标题。
- 保存投递 URL 与证据 URL；清除 `utm_*`、`spm`、`from` 等跟踪参数。
- 明确区分事实、从 JD 得出的推断，以及给用户的建议。

## 与 Agent 的行动契约

- 搜索和读取公开网页属于低风险只读行动，可在用户要求找岗位时执行。
- 投递、发送简历、订阅通知、创建日历或向飞书写入属于外部写操作，必须获得用户确认。
- 检索后先展示不超过三个高优先级机会；完整清单可按用户需要展开。
- 若没有可核验来源，返回“未核验线索”或“资料不足”，不得生成不存在的岗位。

## 入库输出

输出纯 JSON 数组，不要用 Markdown 表格代替机器记录。每条记录至少包含：

```json
{
  "company_name": "单位或公司名称",
  "role_title": "来源中的岗位名称",
  "locations": ["北京"],
  "source_url": "https://official.example/jobs/123",
  "apply_url": "https://official.example/jobs/123/apply",
  "source_level": "S",
  "status": "active",
  "organization_type": "central_soe",
  "employment_type": "enterprise_contract",
  "recruiting_type": "soe_campus"
}
```

岗位内容更新后仍保留同一个来源 URL；轻量流水线会使用内容哈希判断是否需要重建索引。

