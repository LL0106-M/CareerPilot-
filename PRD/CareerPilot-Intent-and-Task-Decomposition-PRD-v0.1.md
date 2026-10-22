# CareerPilot 用户意图识别与任务拆解 PRD v0.1

> 状态：共创草案，等待用户场景与真实语料补充
>
> 上游产品文档：[CareerPilot MVP PRD v1.0](./CareerPilot-MVP-PRD-v1.0.md)
>
> 适用范围：前台对话的意图理解、槽位管理、任务拆解与能力路由
>
> 不包含：模型选型、Prompt 实现、向量数据库选型、Runtime 内部代码设计

## 1. 文档目的

本文定义 CareerPilot 如何把用户的自然表达转化为可执行、可追踪、可纠正的任务状态，重点回答：

1. 用户这一轮真正需要什么；
2. 用户正在完成哪类职业任务；
3. 当前已知、缺失和存在歧义的信息是什么；
4. 系统应该直接回答、追问、检索还是调用工具；
5. 一个复杂请求应如何拆成可完成、可验证的步骤；
6. 哪些内容只属于当前任务，哪些内容可以成为长期记忆候选。

核心原则：

> 意图决定任务方向，槽位描述当前任务状态，路由决定调用哪些能力，Runtime 负责执行；模型提供语义判断，Harness 执行权限与安全约束。

## 2. 产品问题

职业对话很少是单一、完整、明确的命令。用户可能同时表达情绪、提出问题、引用过去经历，并隐含一个尚未成形的行动目标。

例如：

> “腾讯二面又挂了，我现在很怀疑自己，但还是想看看有没有更适合我的产品岗。”

这条消息同时包含：

- 情绪支持需求：被理解，避免立刻说教；
- 求职任务：发现和筛选产品岗位；
- 认知任务：重新判断岗位匹配，而不是直接认定“能力不行”；
- 记忆需求：可能需要过去确认过的城市、行业和稳定性偏好；
- 信息缺口：是否现在就开始搜索、目标城市和招聘类型尚不明确。

如果系统只做单标签分类，会丢失复合需求；如果每次都把所有信息交给大模型自由决定，又会造成检索浪费、工具越权、记忆污染和行为不可评估。

## 3. 产品目标与非目标

### 3.1 产品目标

- 识别一轮对话中的支持方式、主任务和次要任务；
- 将任务所需信息表达为可继承、可确认、可清除的槽位；
- 在信息不足时判断“可以带假设继续”还是“必须先追问”；
- 生成受权限约束的检索计划与能力路由；
- 将复杂目标拆成低认知负担、结果可验证的步骤；
- 支持用户修正系统对意图、槽位和任务的理解；
- 为 Intent、RAG、Memory 和 Tool Routing 建立可独立评估的产品契约。

### 3.2 非目标

- 不为每类意图创建一个独立 Agent；
- 不要求每个槽位都填满后才能回答；
- 不把一次性查询参数自动写入长期记忆；
- 不让模型输出直接成为工具权限；
- 不在 MVP 中处理自动投递、代发消息或不可逆外部操作；
- 不尝试穷举用户所有职业表达。

## 4. 核心用户任务

### 4.1 Job to Be Done

> 当我的职业问题还很模糊、表达中夹杂情绪和不确定信息时，我希望 CareerPilot 能理解我当前最需要解决的事情，利用已经确认的背景补全上下文，只在必要时追问，并把问题拆成我能够继续推进的小步骤。

### 4.2 P0 用户故事

1. 当我只想倾诉时，系统不会因为识别到求职关键词就立即搜索岗位或安排任务。
2. 当我提出明确职业问题时，系统能够判断需要个人记忆、我的资料、公共职业知识还是最新外部信息。
3. 当我的请求包含多个目标时，系统能够说明当前优先处理什么，并保留后续任务。
4. 当缺少关键信息时，系统只追问最影响结果的一个问题，而不是连续盘问。
5. 当系统错误理解我的目标或条件时，我可以自然语言纠正，后续步骤立即使用新状态。
6. 当一个目标需要多个步骤时，系统先给出可理解的任务结构，再逐步推进并反馈进度。

## 5. 意图模型

CareerPilot 不使用单一意图标签，而使用三层意图框架。

### 5.1 第一层：支持模式 Support Mode

支持模式回答“这一轮以什么方式与用户互动”。现有四种模式继续保留：

| 模式 | 用户需要 | 默认行为 | 工具边界 |
|---|---|---|---|
| `listen` | 倾诉、被理解 | 反映感受，最多一个轻问题 | 禁止检索和行动工具 |
| `organize` | 理清事实和困扰 | 区分事实、感受、猜想和未知 | 可读取相关 Memory |
| `explore` | 比较方向、形成假设 | 组织证据、反证和待验证问题 | 可使用受治理 RAG |
| `act` | 推进一步 | 形成一个完成标准明确的动作 | 外部写操作仍需确认 |

优先级：用户显式选择 > 当前轮明确表达 > 系统推断。出现负面情绪不必然等于 `listen`，存在可执行任务也不允许系统自动升级到 `act`。

### 5.2 第二层：任务意图 Task Intent

任务意图回答“用户正在解决什么职业问题”。一轮允许一个主意图和零到多个次意图。

#### P0 意图集合

| Intent | 用户目标 | 典型表达 | 默认结果 |
|---|---|---|---|
| `emotional_support` | 消化求职相关情绪 | “我被拒了，很难受” | 被理解、稳定当前体验 |
| `career_direction` | 探索职业方向 | “我适合产品还是运营” | 候选方向、证据和未知 |
| `job_discovery` | 查找可能适合的岗位 | “看看上海还有哪些产品岗” | 有条件和来源的岗位集合 |
| `job_comparison` | 比较岗位或机会 | “这两个 offer 怎么选” | 比较维度、差异和待验证项 |
| `resume_review` | 诊断简历 | “我的简历哪里有问题” | 有证据的修改优先级 |
| `resume_tailoring` | 针对 JD 调整简历 | “按这个岗位改一下项目经历” | 基于真实经历的定向草稿 |
| `interview_preparation` | 准备面试 | “下周业务面怎么准备” | 准备范围、材料和练习任务 |
| `interview_review` | 复盘面试 | “帮我复盘刚才的二面” | 事实、表现证据和改进假设 |
| `offer_decision` | 做机会选择 | “国企和互联网 offer 怎么选” | 约束与权衡，不替用户决策 |
| `career_planning` | 制定阶段计划 | “未来三个月怎么准备秋招” | 分阶段目标与验证动作 |
| `profile_update` | 补充或纠正个人背景 | “以后只考虑上海” | 结构化候选，必要时确认写入 |
| `general_question` | 询问一般职业知识 | “产品经理主要做什么” | 有来源或明确边界的回答 |

#### 多意图规则

- 必须输出 `primary_intent`；
- 次要意图仅在会影响回复方式、检索或后续任务时保留；
- 默认优先处理用户显式请求；
- 高情绪强度可以调整表达顺序，但不能静默删除明确任务；
- 两个高成本任务并列且优先级不明时，应请求用户选择；
- 可以先完成低成本澄清，再继续主任务。

### 5.3 第三层：操作意图 Operation Intent

操作意图回答“系统下一步应该采取哪种能力”。它不是用户画像，也不直接代表工具授权。

| Operation | 说明 |
|---|---|
| `respond_only` | 基于当前上下文直接回复 |
| `clarify` | 追问一个阻塞任务的关键信息 |
| `retrieve_memory` | 召回长期用户事实或偏好 |
| `retrieve_cognitive_state` | 读取待验证方向、证据和假设 |
| `search_private_documents` | 检索用户简历、JD 或笔记 |
| `search_career_knowledge` | 检索受治理职业知识库 |
| `search_jobs` | 查询结构化岗位库 |
| `search_web` | 查询需要时效性的公开信息 |
| `compare_options` | 对候选项按用户约束进行比较 |
| `generate_draft` | 生成简历、回答或计划草稿 |
| `propose_memory_update` | 产生长期记忆写入候选 |
| `propose_action` | 生成内部行动建议，不直接外部执行 |

## 6. 槽位与任务状态

### 6.1 槽位分类

| 类型 | 示例 | 生命周期 | 默认存储位置 |
|---|---|---|---|
| 当前轮槽位 | “这次先看杭州” | 当前 Turn | Runtime Trace |
| 当前任务槽位 | 本次岗位搜索的角色、城市 | 当前 Task/Session | Session State |
| 稳定用户事实 | 毕业年份、专业 | 跨会话 | MemOS 候选 |
| 稳定用户偏好 | 长期只考虑上海 | 跨会话 | MemOS 候选 |
| 认知假设 | 可能更重视稳定节奏 | 待验证 | Cognitive State |
| 外部事实 | 某岗位截止日期 | 按来源时效 | RAG/Product State |

### 6.2 通用槽位

| Slot | 类型 | 示例 | 说明 |
|---|---|---|---|
| `user_goal` | string | 找到适合的校招产品岗 | 本轮可操作目标 |
| `career_stage` | enum | 校招、社招、转行 | 不明确时可从 Profile 候选补全 |
| `target_roles` | list | 产品经理、产品运营 | 支持多个候选 |
| `target_industries` | list | AI、消费电子 | 可选 |
| `target_companies` | list | 腾讯、华为 | 可选 |
| `locations` | list | 上海、杭州 | 区分本次条件和长期偏好 |
| `organization_types` | list | 央企、民营 | 可选 |
| `time_horizon` | object | 三个月内 | 计划和时效检索使用 |
| `constraints` | list | 不接受长期出差 | 必须保留原始表述和来源 |
| `desired_output` | enum | 列表、比较、计划、草稿 | 可从请求推断 |
| `evidence_scope` | enum | 个人资料、公共知识、最新信息 | 决定检索范围 |

### 6.3 意图专属槽位示例

#### Job Discovery

```json
{
  "role_families": ["产品"],
  "locations": ["上海", "杭州"],
  "recruiting_type": "campus",
  "organization_types": ["central_soe", "local_soe"],
  "deadline_constraint": "open",
  "must_have_constraints": [],
  "nice_to_have_preferences": []
}
```

#### Interview Preparation

```json
{
  "company": "腾讯",
  "role": "产品经理",
  "interview_round": "业务二面",
  "scheduled_at": null,
  "job_description_available": true,
  "resume_available": true,
  "focus_areas": ["项目经历", "产品分析"]
}
```

### 6.4 槽位状态

每个槽位不仅保存值，还必须保存状态：

```json
{
  "name": "locations",
  "value": ["上海"],
  "source": "current_message",
  "confidence": 0.98,
  "scope": "current_task",
  "confirmation": "explicit",
  "updated_at": "2026-10-22T16:00:00+08:00"
}
```

`source` 至少区分：`current_message`、`session`、`memory`、`profile`、`inferred`。当前表达与历史内容冲突时，当前表达优先，但不得静默覆盖长期记录。

### 6.5 最小充分信息原则

每个任务意图定义：

- `required_slots`：缺失后无法产生可信结果；
- `optional_slots`：能够提升结果，但不能阻止任务启动；
- `recoverable_slots`：可以从 Session、Profile 或 Memory 补全；
- `confirmation_slots`：涉及长期偏好或外部动作时必须确认。

只有缺失 `required_slots` 且不能安全恢复时才追问。一次默认只追问一个对结果影响最大的槽位。

## 7. 任务拆解

### 7.1 拆解目标

任务拆解不是生成冗长计划，而是把复杂目标转成有依赖关系、可观察和可停止的步骤。每个步骤必须说明：

- 要解决的问题；
- 所需输入和前置条件；
- 使用的能力；
- 是否需要用户确认；
- 完成标准；
- 失败或信息不足时如何降级。

### 7.2 任务结构

```json
{
  "task_id": "task_123",
  "goal": "找到值得进一步了解的上海产品岗位",
  "status": "active",
  "current_step_id": "step_2",
  "steps": [
    {
      "id": "step_1",
      "title": "确认搜索边界",
      "operation": "clarify",
      "depends_on": [],
      "completion_criteria": "已获得角色范围或用户接受默认假设",
      "status": "completed"
    },
    {
      "id": "step_2",
      "title": "检索开放岗位",
      "operation": "search_jobs",
      "depends_on": ["step_1"],
      "completion_criteria": "获得有来源且仍开放的候选岗位",
      "status": "running"
    },
    {
      "id": "step_3",
      "title": "按个人约束形成候选列表",
      "operation": "compare_options",
      "depends_on": ["step_2"],
      "completion_criteria": "每个候选包含匹配点、风险和待验证项",
      "status": "pending"
    }
  ]
}
```

### 7.3 拆解规则

1. 简单问答不创建多步骤任务；
2. 默认只激活一个主任务，其余作为 `queued`；
3. 每个步骤应能在一次 Run 或一次明确的用户反馈后改变状态；
4. 只拆当前可见的必要步骤，不一次生成数十步远期计划；
5. 需要外部写入或不可逆行为的步骤必须设置确认点；
6. 检索结果不足时允许返回 `partial`，不得用猜测补齐；
7. 用户改变目标时应重规划未执行步骤，已完成证据保留；
8. 情绪支持可以成为回复前置行为，但不伪装成后台任务。

### 7.4 任务状态

```text
proposed → active → running → completed
                    ├─ blocked
                    ├─ partial
                    ├─ cancelled
                    └─ superseded
```

- `blocked`：缺少用户输入、权限或外部依赖；
- `partial`：在预算内获得部分可信结果；
- `cancelled`：用户明确取消；
- `superseded`：用户的新目标替代旧任务，但历史不删除。

## 8. 路由与检索计划

### 8.1 路由原则

- 路由的是能力，不是不同人格或多个 Agent；
- 本地、私有、低成本来源优先；
- 只有明确需要时效性或本地证据不足时才联网；
- Support Mode、用户权限和数据边界可以否决模型建议；
- 检索计划必须记录为什么查、查什么和停止条件。

### 8.2 路由决策表

| 条件 | 默认路由 |
|---|---|
| 用户明确只想倾诉 | `respond_only`，禁止工具 |
| 需要长期个人偏好 | `retrieve_memory` |
| 需要方向假设与历史证据 | `retrieve_cognitive_state` |
| 涉及用户简历、JD、笔记 | `search_private_documents` |
| 通用职业知识 | `search_career_knowledge` |
| 结构化岗位查询 | `search_jobs` |
| 截止时间、最新招聘状态 | 本地证据不足后 `search_web` |
| 缺少阻塞性必要槽位 | `clarify` |
| 明确稳定偏好或“请记住” | `propose_memory_update` |
| 外部写操作 | 请求确认；MVP 默认不执行 |

### 8.3 标准输出：Intent Frame

```json
{
  "support_mode": "organize",
  "primary_intent": "job_discovery",
  "secondary_intents": ["emotional_support"],
  "confidence": 0.86,
  "slots": {},
  "missing_critical_slots": [],
  "ambiguities": [],
  "retrieval_plan": {
    "memory": true,
    "cognitive_state": false,
    "private_documents": true,
    "career_knowledge": false,
    "jobs": true,
    "web": false
  },
  "next_operation": "search_jobs",
  "requires_confirmation": false,
  "reason_codes": ["explicit_job_search", "personal_constraints_needed"]
}
```

Intent Frame 是候选语义判断。最终 Tool Allowlist、数据范围和写入权限由 Harness 的确定性策略生成。

## 9. 端到端流程

```text
接收用户输入
→ 读取显式模式与当前 Session Task
→ 规则处理强约束、安全和用户明确指令
→ 生成 Intent Frame 候选
→ 合并当前消息、Session、Profile 与 Memory 槽位
→ 检测冲突、歧义和必要槽位缺失
→ 直接回复 / 追问 / 生成 Retrieval Plan
→ Context Compiler 按计划组装上下文
→ Runtime 执行模型与工具循环
→ 更新任务步骤状态
→ 生成 Memory Candidate，而不是直接写长期记忆
→ 记录意图、路由、纠正和结果事件
```

## 10. 关键交互案例

### 10.1 情绪与任务并存

用户：“二面又挂了，真的很难受，不过明天还有一场，帮我看看怎么准备。”

- Support Mode：`organize` 或用户显式选择的模式；
- Primary Intent：`interview_preparation`；
- Secondary Intent：`emotional_support`；
- 行为：先简短回应情绪，再推进明天的准备；
- 不应：只安慰而忽略明确任务，或直接生成与目标岗位无关的通用题库。

### 10.2 临时条件与长期偏好

用户：“这次先只看杭州的岗位。”

- `locations=[杭州]`；
- Scope：`current_task`；
- 不写入长期偏好；
- 不应覆盖历史上已确认的长期城市偏好。

### 10.3 必须澄清

用户：“帮我改一下。”但当前会话中没有明确对象。

- Primary Intent：低置信度；
- Next Operation：`clarify`；
- 问题：“你想修改刚才的简历项目描述，还是岗位筛选条件？”
- 不应：自行选择对象并产生大段内容。

### 10.4 可以带假设继续

用户：“产品经理一般需要什么能力？”

- Primary Intent：`general_question`；
- 无需先追问行业和公司；
- 可以提供通用框架，并说明具体岗位会有差异。

## 11. 纠错与控制权

用户必须能够通过自然语言完成：

- 否认意图：“我不是想找工作，只是想了解这个岗位”；
- 修改槽位：“不是上海，是杭州”；
- 改变范围：“先别看互联网公司”；
- 切换模式：“先别给建议，听我说”；
- 取消任务：“这个先不做了”；
- 拒绝记忆：“这只是这次的条件，不要记住”。

纠错要求：

- 当前轮立即生效；
- 未执行步骤按新状态重规划；
- 已产生的外部证据保留来源，但不再作为当前条件；
- 长期记忆冲突进入更新或确认流程，不静默覆盖；
- 记录 `intent_corrected`、`slot_corrected` 或 `task_cancelled` 事件用于评估。

## 12. 降级与失败语义

| 场景 | 产品行为 |
|---|---|
| 意图置信度低但可安全回答 | 给出有限回答，并暴露关键假设 |
| 两个主任务优先级不明 | 询问用户先处理哪个 |
| 结构化识别失败 | 使用确定性规则和 `organize` 默认模式，不调用高风险工具 |
| Memory 不可用 | 仅使用当前消息与 Session，不声称记得历史 |
| RAG 不可用 | 返回无检索降级回答或 `partial` |
| 工具权限不足 | 说明未执行，并提供用户可选的下一步 |
| 任务达到步数/时间预算 | 返回已完成部分、未完成项和停止原因 |

## 13. 指标与评估

### 13.1 离线组件指标

- 主意图 Macro-F1；
- 次要意图多标签 Precision / Recall；
- Support Mode 准确率及高风险误升级率；
- 槽位值 Exact Match / F1；
- 槽位来源、Scope 和确认状态准确率；
- 必须追问识别准确率；
- Retrieval Plan 各能力 Precision / Recall；
- Tool Allowlist 越权率；
- 任务拆解步骤必要性与依赖正确率。

### 13.2 在线产品指标

- 用户首轮纠正意图或槽位的比例；
- 单任务平均澄清轮数；
- 无必要追问率；
- 工具误调用率与无效检索率；
- 一次完成率、`partial` 率和 `blocked` 率；
- 从表达目标到完成一个现实验证动作的转化率；
- 用户对“理解了我现在要做什么”的评分；
- Memory 错写和任务临时条件误写为长期偏好的比例。

### 13.3 P0 上线门槛

- `listen` 明确指令下行动工具误调用率为 0；
- 外部写入操作无法由 Intent Frame 直接授权；
- 跨用户槽位、Memory 和私有资料泄漏为 0；
- 当前表达与历史冲突时不静默采用历史值；
- P0 意图和关键槽位具备覆盖正常、模糊、多意图、纠错和对抗表达的评估集；
- 低置信度和解析失败都有确定性降级路径。

## 14. MVP 范围与里程碑

### M0：定义与数据集

- 冻结 P0 Intent Taxonomy；
- 为每个 Intent 定义 required/optional/recoverable slots；
- 收集和标注首批真实或脱敏表达；
- 定义 Intent Frame JSON Schema；
- 建立规则基线与离线评估脚本。

### M1：单轮意图与路由

- 规则 + 结构化模型的两阶段识别；
- 输出 Support Mode、Task Intent、Slots 和 Retrieval Plan；
- Harness 根据策略生成 Tool Allowlist；
- Runtime 记录意图和路由事件。

### M2：跨轮任务状态

- Session 级 Slot 合并、冲突和清除；
- Task/Step 状态持久化；
- 支持用户纠正、取消和切换任务；
- 支持 `blocked`、`partial` 和 `superseded`。

### M3：Memory 联动与在线评估

- 稳定事实/偏好进入 Memory Candidate；
- 当前任务槽位与长期偏好严格分离；
- 上线纠错、无效检索和任务完成指标；
- 基于封测数据调整 Taxonomy 与槽位定义。

## 15. 待共创内容

以下内容需要结合目标用户访谈、真实对话和产品取舍继续撰写：

1. P0 Intent 是否覆盖最重要的前三个首发场景；
2. `career_direction` 与 `career_planning` 的产品边界；
3. `resume_review` 与 `resume_tailoring` 是否需要拆开；
4. 岗位搜索的最小必需槽位是什么；
5. 用户在什么情况下愿意确认长期偏好；
6. 多任务并列时是自动排序还是始终让用户选择；
7. 哪些 Task 应进入产品任务列表，而不是只留在 Session；
8. Intent Frame 是否需要向用户可视化，以及展示到什么粒度。

## 附录 A：单个 Intent 撰写模板

```markdown
### Intent 名称

- Intent ID：
- 用户目标：
- 典型触发表达：
- 容易混淆的 Intent：
- 不属于该 Intent 的表达：
- 默认 Support Mode：
- Required Slots：
- Optional Slots：
- Recoverable Slots：
- 必须追问条件：
- 可带假设继续的条件：
- 默认 Retrieval Plan：
- 允许的 Operations：
- 禁止行为：
- 完成标准：
- 失败/降级结果：
- 是否可能产生 Memory Candidate：
- 正例：
- 边界例：
- 反例：
```

## 附录 B：用户语料标注模板

```json
{
  "utterance": "",
  "conversation_context": [],
  "explicit_support_mode": null,
  "primary_intent": "",
  "secondary_intents": [],
  "slots": [],
  "missing_critical_slots": [],
  "expected_retrieval": [],
  "expected_next_operation": "",
  "forbidden_operations": [],
  "expected_clarifying_question": null,
  "memory_candidates": [],
  "annotation_notes": ""
}
```

## 附录 C：待补充的首发场景清单

| 场景 | 目标用户 | Primary Intent | 关键槽位 | 理想结果 | 优先级 |
|---|---|---|---|---|---|
| 被拒后仍需准备下一场面试 |  |  |  |  | P0 |
| 在多个职业方向间犹豫 |  |  |  |  | P0 |
| 根据个人资料寻找岗位 |  |  |  |  | P0 |
| 针对具体 JD 调整简历 |  |  |  |  | P1 |
| 比较两个 Offer |  |  |  |  | P1 |
