# CareerPilot Agent Memory Handbook

这份手册定义 CareerPilot 的 Agent Memory。它是开发合同，不是产品介绍。

## 1. 一句话架构

```text
Event -> Extract -> Policy -> Store/Index -> Retrieve -> Context
                  \-> Dreaming Queue -> Evidence-bound Proposals
                  \-> Domain Event -> Compass/Journey
```

- Memory 负责跨轮次保存和召回用户上下文。
- Compass、Journey、Task、Calendar 是业务状态，不是 Memory。
- Knowledge 保存外部岗位、面经和学习资源，不是用户记忆。
- LLM 只提出候选；策略层决定写入，领域服务决定业务状态。

## 2. 系统边界

| 系统 | 负责 | 不负责 |
|---|---|---|
| Event Store | 追加对话和行为事实 | 推断用户特征 |
| Agent Memory | 用户上下文、经历、偏好、协作方式 | 创建航程、任务和日历 |
| Domain Store | 想法、方向、罗盘、航程、任务、日历 | 语义召回外部资料 |
| Knowledge Store | 岗位、面经、题目、学习资源 | 定义用户是谁 |

任何具体公司或岗位都必须来自当前用户事件或用户已有数据。禁止生产代码预置方向。

## 3. 记忆类型

### Working

当前消息、最近完整轮次、当前页面、当前对象和本轮工具结果。默认不持久化。

### Episodic

带时间和来源的经历，例如一次面试、一次拒绝、一次方向变化。Episode 不得自动升级成人格或稳定偏好。

### Semantic

经证据支持的稳定事实、偏好、约束和明确目标。必须支持冲突、版本和失效。

### Procedural

Agent 与用户协作的方式，例如“隐含方向必须询问后才能加入罗盘”。用户偏好不能覆盖系统安全策略。

### Prospective

未来触发条件和 Agent 承诺，例如“岗位采集完成后刷新当前航程”。正式任务仍存 Domain Store。

## 4. 统一记忆信封

每条长期记忆至少包含：

```text
memory_id, owner_id, kind, content
source_event_ids, entity_refs
authorship, confidence, salience
status, valid_from, valid_until
version, sensitivity, created_at, updated_at
```

`authorship`：

- `user_explicit`：用户明确表达。
- `user_confirmed`：AI 提出，用户确认。
- `ai_inferred`：AI 推测，不能当作用户事实。
- `system_observed`：来自行为证据。
- `external_import`：来自简历或外部资料。

`status`：`candidate | active | superseded | retracted | expired | archived`。

更新不覆盖历史。旧版本变为 `superseded`，新版本成为 `active`。

## 5. 写入协议

```text
append event
  -> LLM returns candidate operations
  -> validate schema and provenance
  -> policy: commit | pending | ignore
  -> deduplicate and resolve conflicts
  -> atomic write and index
```

硬规则：

1. 只有成功完成并持久化的轮次可以学习。
2. LLM 不得直接写数据库。
3. 临时情绪、自我否定和诊断性标签不得成为稳定语义记忆。
4. 用户当前明确表达优先于历史记忆。
5. AI 推测保持候选，除非用户确认或积累足够证据。
6. 删除、撤回和拒绝立即影响召回。

## 6. 读取协议

```text
query analysis
  -> filter by owner, kind, status, scope, sensitivity
  -> lexical + vector + entity retrieval
  -> rerank
  -> remove conflicts and duplicates
  -> context budget packing
```

排序至少考虑：相关性、明确程度、新鲜度、显著性、来源可靠度和当前实体；拒绝、冲突、过期内容降权。

上下文顺序：当前对话 -> 当前页面/对象 -> 活跃航程 -> 已确认方向 -> 稳定事实/偏好 -> 相关 Episode -> 未确认假设 -> 外部知识。

## 7. Consolidation

后台整理可以 merge、supersede、retract、expire，不得凭空创造事实。

- 多次 Episode 可提炼 Semantic Memory。
- 相似内容去重但保留来源集合。
- 冲突内容保留版本，最新明确表达生效。
- 低置信推测随时间衰减。
- 航程结束后压缩成 Episode 总结和少量 Semantic 结论。

所有操作必须幂等，并保留 applied receipt 或审计记录。

## 8. 方向信号协议

Memory Extractor 可以发出 `direction.signal.detected`，但不能直接创建航程。

```text
explicit  -> Direction Service 创建已确认罗盘方向，并告知用户
implicit  -> 返回 ask_to_add，前端在对话侧栏询问
uncertain -> 继续澄清，不写正式方向
none      -> 不触发
```

信号必须包含：`label`、`explicitness`、`source_quote`、`reason`、`confidence` 和 `suggested_action`。

加入罗盘不等于开启航程。航程只能由用户从已确认方向主动启动。

## 9. 前端合同

前端不推断业务状态，只渲染后端返回的数据。

- 没有用户数据时不显示具体公司、岗位或任务。
- 模块没有数据时不渲染空壳。
- AI 建议在用户接受前不能进入任务或日历。
- 后台状态变化必须使相关查询失效或通过事件通知刷新。
- 想法保留首页输入和罗盘中的散落卡片形式。
- 不建设独立记忆管理页；纠正、删除和拒绝发生在对话及具体对象上。

## 10. MemOS

MemOS Cloud 是服务端辅助记忆层，不是业务真相源，也不替代本地统一记忆库。

```text
successful turn
  -> local admission policy
  -> canonical SQLite transaction
  -> MemOS addMessage (private, async, best effort)

new turn
  -> canonical active-memory retrieval
  -> optional MemOS semantic candidate retrieval
  -> local status/deletion/conflict gate
  -> prompt budget
```

- `user_id` 使用登录用户的稳定 `owner_id`；`conversation_id` 使用稳定会话 ID。
- Key 只存在服务端 `MEMOS_API_KEY`，禁止进入浏览器包、日志或数据库。
- 写入使用 `POST /add/message`，检索使用 `POST /search/memory`。
- 仅通过本地写入政策、且回复验证成功的轮次可以写入 MemOS。
- MemOS 超时或 5xx 只把 `memory_provider_status` 标为 `unavailable`；本地成功写入和回复不回滚。
- 本地的 `active/paused/superseded/deleted`、敏感性与 owner 授权始终覆盖云端结果。
- 删除必须先在本地生效；在云端 ID 映射和删除回执完成前，云端结果不能绕过本地状态重新进入 Prompt。

## 11. Dreaming 子系统

Dreaming 是异步认知整理器，不是定时自由联想，也不是第二个聊天 Agent。

### 11.1 触发

允许的触发源：

- 用户明确要求复盘或整理。
- 面试、Offer、拒绝、方向变化等职业里程碑。
- 用户手动启动当日 Dreaming。

普通知识问答、临时情绪和每一轮对话不会自动触发。

### 11.2 作业状态机

```text
queued -> processing -> completed
                    \-> failed
```

同一 owner、同一会话证据和触发类型必须幂等。失败保留有限错误码，可重试，但不能重复应用结果。

### 11.3 Snapshot

Dreaming 只能读取不可变快照：`owner_id`、`conversation_id`、触发原因、用户原话、助手回复、已召回记忆以及证据 ID。快照之外的内容不能被结果引用。

### 11.4 输出

Dreaming 只允许产生三类结构化输出：

1. `HypothesisProposal`：带置信区间、支持证据和待澄清问题的职业假设。
2. `DailyReview`：胜利、阻碍、开放循环和下一小步的回顾。
3. `MemoryPatchProposal`：merge、supersede、retract、expire 等候选操作。

禁止输出人格诊断、无证据技能缺口或伪造的用户目标。

### 11.5 应用门

- Hypothesis 进入候选区，用户确认后才能成为明确方向。
- DailyReview 可以直接保存为回顾，但其中推断仍保持推断标签。
- MemoryPatch 必须通过 owner、证据范围、版本、敏感性和写入政策校验。
- Dreaming 不能创建 Journey、任务、日历或外部动作。

## 12. 在线读取与上下文预算

每轮按照以下顺序组织上下文：安全策略、当前轮次、当前页面/对象、活跃领域状态、本地已确认记忆、相关 Episode、Dreaming 候选、外部知识。MemOS 返回的是不可信候选；当前用户原话和本地 active 状态优先。

任何单一来源不可占满上下文。事实、偏好、Episode、假设和外部知识分别限额，重复内容按来源可靠度与新鲜度合并。

## 13. 故障与降级

| 故障 | 行为 |
|---|---|
| MemOS 搜索超时 | 使用本地记忆继续回复，记录 provider unavailable |
| MemOS 写入失败 | 保留本地提交，进入可重试审计，不影响回复 |
| 本地记忆事务失败 | 不写 MemOS，返回 memory write unavailable |
| Dreaming 模型失败 | 作业标记 failed，不产生任何候选 |
| Dreaming 证据越界 | 拒绝整个分析结果并记录审计 |
| 冲突记忆 | 最新用户明确表达生效，旧版本 superseded |

## 14. 上线配置

生产环境必须提供：`MEMOS_API_KEY=mpg-...`；可选覆盖 `MEMOS_BASE_URL`。启动时校验 Key 形状但不输出原值。发布前必须完成合成数据的 add/search smoke test、MemOS 5xx 降级测试、owner 隔离测试及本地删除不可被云端召回的测试。

## 15. 完成标准

一次 Memory 变更只有在以下条件全部满足时完成：

- 有原始事件和来源引用。
- 有明确的写入策略结果。
- owner 隔离测试通过。
- 冲突、撤回和重复写入行为有测试。
- 前端显示来自真实 API 数据。
- 刷新后状态一致。
- 没有具体公司或岗位硬编码。
