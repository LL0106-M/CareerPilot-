# CareerPilot DREAMING Idea

> 状态：产品构想草案
>
> 当前切入点：每日求职申请总结
>
> 目的：保存 Dreaming、每日陪伴、小胜利、阻碍与职业航向之间的产品构想，暂不作为正式 MVP 承诺

## 1. 核心构想

CareerPilot 的 Dreaming 不只做后台记忆压缩。它可以在事实和证据充分的前提下，帮助用户看见：

- 今天实际推进了什么；
- 哪些微小行动值得被承认；
- 哪些阻碍正在重复出现；
- 哪些新想法值得保留但不必立即执行；
- 当前行动是否正在为某个职业航向增加证据；
- 明天最值得推进的一个低压力动作是什么。

第一版从“每日求职申请总结”开始，因为申请、状态变化和截止日期是结构清晰、容易验证的事实。

```text
Daily Digest      让用户看见今天发生了什么
Weekly Dreaming   帮助用户理解这些行动说明了什么
Navigation Review 帮助用户判断下一阶段往哪里走
```

## 2. 产品边界

需要区分三个职责：

```text
Dreaming / Consolidation
  聚合事件、发现模式、生成有证据的总结或 Proposal

Digest Product
  决定向用户展示哪些内容以及如何交互

Scheduler / Notification
  决定何时生成、何时推送以及是否重试
```

本构想不会把 Dreaming 简化为一条每日通知。Memory Consolidation 仍然是后台记忆巩固能力；Daily Digest 是第一个面向用户的产品出口。

Dreaming 不得：

- 根据一次失败形成长期人格判断；
- 自动修改用户航向或长期目标；
- 自动把每个想法变成任务；
- 自动将临时状态写入长期记忆；
- 自动执行外部操作；
- 在没有事实依据时生成进展、阻碍或申请状态。

## 3. 第一版：每日申请总结

每天在用户设定的本地时间，CareerPilot 汇总自上次 Digest 后的求职申请活动。

### 3.1 内容结构

```text
今日申请
├─ 新增了哪些申请
├─ 哪些申请完成投递
├─ 哪些申请状态发生变化
├─ 哪些岗位即将截止
├─ 今天的小胜利
├─ 当前阻碍
└─ 一个可选的明日动作
```

示例：

> 今天你新增了 3 个申请，其中 2 个已经完成投递，另一个还缺少作品集链接。完成岗位筛选和两次投递，本身就是明确的推进。当前最直接的阻碍是作品集材料尚未准备好。明天如果愿意，可以只花 15 分钟选定一个项目链接，不需要一次完成整份作品集。

### 3.2 事实与生成分离

申请数量、状态、截止日期和已完成动作必须来自结构化 Product State，不能由模型根据对话猜测。

```text
Application Store
→ Daily Aggregator 生成确定性事实
→ Dreaming 组织意义、小胜利和阻碍
→ Verifier 检查每项陈述的证据
→ Digest Store
→ Notification Scheduler
```

事实层示例：

```json
{
  "local_date": "2026-10-22",
  "new_applications": 3,
  "submitted": 2,
  "incomplete": 1,
  "status_changes": [],
  "upcoming_deadlines": [
    {
      "company": "某央企",
      "role": "数字化产品岗",
      "deadline": "2026-10-24"
    }
  ],
  "completed_actions": [
    "完成岗位筛选",
    "完成两次投递"
  ],
  "unfinished_actions": [
    "补充作品集链接"
  ]
}
```

### 3.3 Dreaming 的首版职责

第一版只承担四项产品责任：

1. 将确定性申请事实组织成简短总结；
2. 从真实完成事件中识别一个或多个小胜利；
3. 从延期、缺失材料或用户明确表达中识别阻碍；
4. 根据当前唯一关键阻碍建议一个低压力下一步。

建议不是任务。只有用户选择“加入明日计划”，系统才创建 Action。

## 4. 数据归属

申请、总结、小胜利和阻碍不能全部写进 MemOS。

| 信息 | 负责系统 |
|---|---|
| 公司、岗位、申请状态和时间 | Application/Product Store |
| 每日申请总结 | Digest Store |
| 已完成的小推进 | Progress Event / Small Win |
| 影响行动的阻碍 | Friction Event / Blocker |
| 当前行动与明日计划 | Action Store |
| 航向、候选方向和阶段重点 | Navigation Store |
| 稳定用户事实与长期偏好 | MemOS |
| 系统尚未确认的模式判断 | Cognitive Hypothesis |
| 岗位原文和公开招聘证据 | Job Store / RAG |

申请记录示例：

```json
{
  "application_id": "app_123",
  "user_id": "u1",
  "company": "腾讯",
  "role": "AI 产品经理",
  "job_id": "job_456",
  "status": "submitted",
  "submitted_at": "2026-10-22T15:30:00+08:00",
  "deadline": "2026-10-25",
  "source_url": "https://example.com/job",
  "next_action": null
}
```

状态变化以事件记录：

```json
{
  "type": "application_status_changed",
  "application_id": "app_123",
  "from": "preparing",
  "to": "submitted",
  "occurred_at": "2026-10-22T15:30:00+08:00"
}
```

## 5. 小胜利

陪伴型产品不能只记录任务成功或失败。以下都可以是小胜利：

- 完成一次投递；
- 只修改了一段简历；
- 主动联系一位学长；
- 明确排除了一个不适合的方向；
- 说清楚了自己真正担心什么；
- 取消了一个不合理的目标；
- 在精力有限时仍完成一个极小动作。

小胜利需要事件证据，也需要允许用户赋予意义。

```json
{
  "win_id": "win_123",
  "description": "完成了产品项目经历的第一版改写",
  "win_type": "progress",
  "linked_action_id": "action_22",
  "linked_direction_id": "direction_product",
  "evidence_event_ids": ["event_88"],
  "user_meaning": "终于开始动手，而不是继续纠结",
  "occurred_at": "2026-10-22T20:00:00+08:00"
}
```

## 6. 阻碍

阻碍是一等产品对象，是下一步规划的输入，不是对用户人格的评价。

首版分类：

```text
clarity       不知道怎么做
task_scope    任务过大
energy        精力不足
emotion       害怕、羞耻、焦虑
environment   环境干扰
dependency    等待他人或外部资源
skill_gap     暂时缺少能力
resource_gap  缺少资料或工具
conflict      目标之间冲突
```

```json
{
  "blocker_id": "blocker_123",
  "description": "每次开始修改简历都会想一次全部改完",
  "category": "task_scope",
  "severity": "medium",
  "controllability": "partial",
  "recurrence": "repeated",
  "linked_action_id": "action_22",
  "attempted_responses": ["列修改清单"],
  "effective_responses": [],
  "status": "active"
}
```

阻碍对行动的影响：

```text
task_scope 重复出现 → 缩小下一步粒度
energy 重复出现     → 调整时间或降低认知负担
resource_gap         → 优先补齐一个关键资料
dependency           → 创建等待状态而不是催促用户
同类行动持续成功     → 提高这种行动形式的优先级
```

## 7. Idea、Experiment 与行动

用户出现新的产品 Idea 或其他想法时，不立即生成大量任务。建议使用以下生命周期：

```text
captured
→ clarifying
→ incubating
→ selected
→ experimenting
→ validated / rejected / archived
```

Idea 作为 Product State 保存；长篇原文可以进入 Private RAG。Idea 只有在用户愿意推进时才转成 Experiment，再生成一个低压力 Action。

```text
捕获 Idea
→ 关联当前航向
→ 判断用户是否想继续
→ 形成一个可证伪假设
→ 设计最小验证实验
→ 创建一个当前行动
```

示例：

```json
{
  "experiment": {
    "hypothesis": "应届生愿意每天记录一个求职小胜利",
    "method": "访谈 3 位正在求职的同学",
    "estimated_minutes": 30,
    "success_criteria": "至少 2 人能描述持续记录的价值",
    "linked_idea_id": "idea_123"
  }
}
```

## 8. 航向闭环

CareerPilot 的航向不是任务列表，而是一个证据循环：

```text
Direction 航向
→ Hypothesis 方向假设
→ Idea 新想法
→ Experiment 最小实验
→ Action 当前行动
→ Outcome
   ├─ Small Win
   ├─ Blocker
   ├─ Learning
   └─ Evidence
→ Dreaming / Reflection
→ Navigation Update Proposal
→ 用户确认、否认或继续验证
```

小胜利和阻碍可以改变后续 Planning Policy，但不能自动改变用户航向。

## 9. Daily、Weekly 与 Navigation Review

### 9.1 Daily Digest

目标是轻量陪伴和看见真实推进：

```text
今天发生了什么
一个小胜利
一个当前阻碍
一个可选的下一步
```

### 9.2 Weekly Dreaming

目标是发现可验证模式：

```text
行动集中在哪些方向
哪些阻碍反复出现
什么样的行动更容易完成
哪些 Idea 反复出现
当前航向获得了哪些支持或反证
```

所有模式只能作为 Proposal，并提供支持证据、反证和置信度。

### 9.3 Navigation Review

低频检查：

```text
方向是否发生变化
偏好是否发生变化
哪些假设得到验证
哪些目标适合继续、暂停或放弃
```

## 10. 无活动时的策略

不要机械推送“今天投递 0 个岗位”。

```text
有有效进展   → 完整总结
只有浏览收藏 → 轻量总结
没有活动     → 默认不推送，或按用户偏好轻问一句
连续无活动   → 询问是否需要调整计划，不做负面评价
```

用户必须能设置：

- 是否开启每日总结；
- 推送时间和时区；
- 免打扰时间；
- 无活动时是否推送；
- 是否展示小胜利；
- 是否提供下一步建议；
- 锁屏通知是否显示公司和岗位名称。

默认锁屏通知只显示“你的今日求职总结已生成”，详细内容在产品内查看。

## 11. 调度、幂等与降级

```text
用户本地时间到达
→ 获取上次 Digest 后的新事件
→ 生成确定性事实摘要
→ Dreaming 生成自然语言与 Proposal
→ Verifier 校验证据
→ 保存 Digest
→ 发送产品内通知或系统推送
```

建议幂等键：

```text
daily_application_digest:{user_id}:{local_date}
```

降级规则：

- 模型不可用时使用确定性模板；
- 任务重试不能重复推送；
- 没有可信数据时不生成虚假总结；
- 数据不完整时明确标记 `partial`；
- 通知失败不影响已生成 Digest；
- 用户关闭推送后仍可选择仅保留产品内总结。

## 12. Digest 数据结构草案

```json
{
  "digest_id": "digest_123",
  "user_id": "u1",
  "digest_type": "daily_application",
  "local_date": "2026-10-22",
  "facts": {},
  "small_wins": [],
  "blockers": [],
  "suggested_next_action": null,
  "evidence_event_ids": [],
  "generation_status": "completed",
  "delivery_status": "pending",
  "created_at": "2026-10-22T21:30:00+08:00"
}
```

## 13. MVP 建议

第一版只做：

1. 用户手动记录或系统内部产生申请；
2. 保存申请状态变化；
3. 每日聚合确定性事实；
4. 识别有证据的小胜利和阻碍；
5. 模型生成简短总结；
6. 最多建议一个下一步；
7. 用户确认后才能加入明日计划；
8. 先使用产品内 Inbox 展示，再接系统推送。

暂时不做：

- 自动读取邮箱判断申请状态；
- 自动修改航向；
- 自动写入长期 Memory；
- 每天生成深层人格分析；
- 自动创建大量任务；
- 无活动时高频催促。

## 14. 待验证问题

1. 每日总结的默认发送时间和是否允许用户完全关闭；
2. 用户是否愿意手动维护申请状态；
3. “小胜利”由系统识别、用户记录，还是两者结合；
4. 阻碍是否应主动询问，还是只从已有证据提议；
5. 用户对无活动日总结的接受程度；
6. 每日建议一个行动是否会增加压力；
7. Weekly Dreaming 的 Proposal 是否需要显式确认；
8. 哪些 Digest 内容适合进入长期 Memory；
9. Daily Digest 与现有任务、航向页面如何联动；
10. 何时从产品内 Inbox 扩展到系统 Push。
