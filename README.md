<div align="center">

# CareerPilot

### 把模糊的职业想法，变成可以验证、可以复盘的下一步。

**一个会记住你、会查证据，也知道什么时候不该替你做决定的长期职业陪伴 Agent。**

[![status](https://img.shields.io/badge/status-MVP-3f7562?style=flat-square)](https://careerpilot.pages.dev)
[![frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-7899ae?style=flat-square)](./frontend)
[![backend](https://img.shields.io/badge/backend-FastAPI-d4a85f?style=flat-square)](./src/careerpilot)
[![benchmark](https://img.shields.io/badge/memory%20benchmark-10%2F10-795f52?style=flat-square)](./docs/evaluation/README.md)

### [打开 CareerPilot 在线体验 →](https://careerpilot.pages.dev)

[产品与使用方式](#careerpilot-如何工作) · [完整产品拆解](docs/product/careerpilot-product-teardown.md) · [技术架构](docs/architecture/README.md) · [评测报告](docs/evaluation/README.md) · [本地运行](#本地运行)

</div>

[![CareerPilot 产品首页：泊泊在山林湖泊前陪伴用户探索职业方向](docs/assets/careerpilot-product-home.png)](https://careerpilot.pages.dev)

> **You don't choose a future. You learn your way into one.**
>
> CareerPilot 不急着给你一个职业答案。它把对话里真正重要的线索、外部职业证据和现实行动连起来，让方向在一次次验证中逐渐清晰。

## CareerPilot 如何工作

CareerPilot 不是一个“问完即走”的职业问答机器人。它通过三条彼此连接的链路，让一次聊天能够沉淀为长期理解，让一个想法能够走到现实行动，再让行动结果反过来修正方向。

### 1️⃣ 对话理解链：先理解你，再决定要不要推进

```text
你说出困惑或经历
→ Agent 判断此刻更需要倾听、梳理、探索还是行动
→ 召回与当前问题真正相关的历史
→ 回应当前问题
→ 提炼值得长期保留的记忆候选
→ 由写入策略和用户控制决定是否保留
```

你可以说：“我好像喜欢 AI 产品，但也可能只是害怕错过。”CareerPilot 不会立刻给你贴上“适合产品经理”的标签。它会先区分兴趣、焦虑、已有经历和现实约束；一次性的自责不会被固化成性格，稳定偏好和明确目标才有机会进入长期记忆。

记忆不是模型可以随意改写的黑箱。后端提供查看、纠正、暂停和删除能力；当前产品界面主要通过对话与 Dreaming 暴露候选洞察，独立记忆管理入口仍在完善。当前表达与旧记忆冲突时，以当前表达为准。

[了解完整产品使用方式 →](docs/product/README.md#1-从一句真实想法开始)

### 2️⃣ 方向验证链：用证据养大一个职业猜想

```text
模糊想法
→ 候选方向信号
→ 用户确认后进入「罗盘」
→ 组织支持证据、反证和未知项
→ 从个人资料与职业知识库检索依据
→ 资料不足或要求时效性时再受控联网
→ 形成可验证的方向判断
```

CareerPilot 把职业方向当成“可以被证伪的假设”，而不是一次测评得出的永久结论。罗盘会同时保留支持证据、反例、未知问题和信心变化；RAG 为岗位能力、招聘规则和学习资源提供可回源依据，并把个人记忆与公共知识分开管理。

例如，比起回答“你适合做 AI 产品经理”，它更关心：“哪些经历支持这个判断？哪些只是想象？下一次需要验证什么？”

[查看 Memory 与 RAG 如何协作 →](docs/architecture/README.md#3-memory--rag同一套上下文系统)

### 3️⃣ 行动反馈链：每次只迈一小步，再让结果改变判断

```text
已确认的方向
→ 生成一个 15—30 分钟、完成标准明确的小行动
→ 用户确认外部写操作
→ 同步到任务、日历或连接器
→ 记录完成、延期、取消和现实反馈
→ Dreaming 整理跨会话变化与冲突
→ 更新记忆、罗盘和下一段航程
```

真正让 Agent 变得“长期”的不是多聊几轮，而是能接住现实反馈。一次访谈、一次项目体验或一次被拒绝，都可以成为新的证据。后台 Dreaming 只基于已有事件提出可审查的总结和假设，不会凭空给用户创建方向，也不会越过确认替用户发送消息或修改日历。

它的自主性体现在整理、召回和提出候选；它的克制体现在高影响判断与外部动作始终把控制权留给用户。

## 用户怎么使用

1. **从当下开始**：在对话中说出最近的困惑、经历或想尝试的方向，不需要先整理好问题。
2. **确认值得探索的方向**：Agent 识别到方向信号后，由你决定是否加入罗盘。
3. **查看证据而不是结论**：在罗盘和知识库中比较个人经历、反证、岗位资料与待验证问题。
4. **开启一段航程**：把方向拆成一个低压力的小行动；涉及日历、邮件等外部写入时先预览、再确认。
5. **带着结果回来**：记录完成、延期、取消和真实感受，让新的证据更新后续判断。

| 入口 | 你可以做什么 |
|---|---|
| **今日** | 查看今天值得关注的线索、行动与进展。 |
| **对话** | 在倾听、整理、探索、行动四种支持模式间自然切换。 |
| **Dreaming** | 回看跨会话变化，确认或拒绝系统提出的候选洞察。 |
| **罗盘** | 管理候选方向、支持证据、反证、未知项与信心。 |
| **航程** | 把方向推进为小行动，并记录现实反馈。 |
| **知识库** | 查看岗位、面试经验、学习资料与个人文档。 |

更完整的场景示例、页面说明和能力边界见 [产品指南](docs/product/README.md)；如果想快速理解产品定位、三大核心机制与适用人群，可阅读 [CareerPilot 产品拆解](docs/product/careerpilot-product-teardown.md)。

## 它特别在哪里

| 常见职业助手 | CareerPilot |
|---|---|
| 用一次测评或一轮对话给出推荐 | 把方向表示成可持续修正的假设 |
| 把聊天记录直接当作“记忆” | 区分事件、稳定记忆、职业认知和产品状态 |
| 有资料就全部塞进上下文 | 先判断意图，再按用途和预算检索 Memory/RAG |
| 用更多建议制造推进感 | 每轮默认只推进一个可承受的小行动 |
| 工具调用即执行 | 外部写操作遵循预览、确认、执行、验证 |
| 只看回答是否像样 | 同时评测回复、运行轨迹、状态变化与安全硬失败 |

## 技术框架

CareerPilot 是一个单前台 Agent、Memory/RAG-native 的自有 Harness。模型负责语义理解与工具选择；Runtime 负责会话、步数、事件和故障边界；确定性策略负责记忆准入、检索范围、工具权限和外部动作确认。

```text
React / Vite
      │
      ▼
FastAPI / AgentService
      │
      ├─ Intent + Context Compiler
      ├─ CareerPilot Runtime（model ⇄ tool）
      ├─ Memory + Cognitive State + Dreaming
      ├─ Governed RAG（private / career / jobs / web）
      ├─ MCP Tool Platform（discover → select → policy → call）
      └─ Action Service（preview → confirm → apply → verify）
```

主文档入口：

- [产品拆解：产品定位、三大核心机制、一句话总结与使用建议](docs/product/careerpilot-product-teardown.md)
- [整体技术架构：组件边界、数据流、Runtime 与 MCP](docs/architecture/README.md)
- [Memory + RAG：记忆、认知状态、知识与检索如何协作](docs/architecture/README.md#3-memory--rag同一套上下文系统)
- [Agent Memory 开发手册：数据类型、写入、冲突、Dreaming](docs/architecture/agent-memory-handbook.md)
- [评测中心：最新报告、数据集与复现方式](docs/evaluation/README.md)
- [完整文档地图：当前文档与历史设计稿的边界](docs/README.md)

## 评测基线

当前公开基线使用冻结语料、独立数据库和生产代码运行，不调用外部模型或网络；安全硬失败单独报告，不用平均分掩盖。

| 系统 | Case | Pass Rate | 关键结果 |
|---|---:|---:|---|
| Memory | 10 | **100.0%** | 召回、用户隔离、敏感信息门控、纠正与去重全部通过 |
| RAG | 8 | **87.5%** | 7/8 通过；待改进项为过期资料抑制 |
| 安全硬失败 | — | **0** | 未发现跨用户泄漏、敏感信息越权暴露或运行异常 |

这里展示的是 2026-11-05 的 MVP 离线基线，不代表真实用户分布，也不等于端到端 Agent 已达到生产标准。查看 [完整评测报告与适用边界](docs/evaluation/README.md)。

## 本地运行

本地模型默认使用 `Qwen3-4B GGUF Q4_K_M`，由 `llama.cpp` 在 CPU 上运行，不需要付费模型 API。首次启动需下载约 2.5 GB 模型权重，并额外下载 Docker 镜像；建议至少 8 GB 内存，16 GB 更稳定。

```powershell
docker compose up -d local-llm
.venv\Scripts\python.exe scripts\smoke_local_model.py

docker compose up -d
.venv\Scripts\python.exe scripts\smoke_deployment.py --base-url http://127.0.0.1:8080
```

完整环境变量、服务检查、停止方式与 MCP 配置见 [本地开发与部署指南](docs/development.md)。

---

<div align="center">

**方向不是一次选出来的，而是在一次次真实尝试中长出来的。**

[现在就和泊泊聊聊 →](https://careerpilot.pages.dev)

</div>
