# CareerPilot 文档地图

文档按“当前入口、专题参考、历史记录”分层。第一次阅读请从前三个入口开始，不需要按文件时间逐个翻阅。

## 当前入口

| 想了解什么 | 从这里开始 |
|---|---|
| 产品是什么、用户如何使用 | [产品指南](product/README.md) |
| 整体架构、Memory/RAG、Runtime、MCP | [技术架构](architecture/README.md) |
| 最新结果、数据集与复现 | [评测中心](evaluation/README.md) |
| 本地运行、部署与 MCP 配置 | [开发与部署](development.md) |

## 当前专题参考

- [Agent Memory Handbook](architecture/agent-memory-handbook.md)：Memory 类型、生命周期、Dreaming、冲突与隐私控制。
- [CareerPilot Harness Architecture](architecture/careerpilot-harness.md)：运行协议、上下文计划、事件与失败语义。
- [CareerPilot MVP PRD](../PRD/CareerPilot-MVP-PRD-v1.0.md)：产品目标、支持模式、自治等级与上线门槛。
- [Memory + RAG Technical Design](../PRD/CareerPilot-Memory-RAG-Technical-Design.md)：详细数据模型、接口和检索设计。
- [Intent and Task Decomposition](../PRD/CareerPilot-Intent-and-Task-Decomposition-PRD-v0.1.md)：意图、槽位和能力路由。
- [AgentEval v2 建构方法](evaluation/careerpilot-agenteval-v2-construction.md)：端到端任务与判分设计。
- [RAG 与 Memory 基准建构说明](evaluation/careerpilot-system-benchmark-design.md)：冻结数据集和指标设计。

## 历史设计与实施记录

`docs/superpowers/specs/` 保存阶段性设计选择，`docs/superpowers/plans/` 保存对应的实施计划。这些文件用于追溯“当时为什么这样做”，不会从主 README 逐份索引。

当历史记录与当前入口冲突时，判断优先级为：

```text
当前代码与测试
→ architecture / evaluation 当前入口
→ 专题手册与当前 PRD
→ 历史 specs / plans
```

`docs/plans/` 中的早期设计同样视为历史材料。除非正在追溯某项实现，不建议把历史计划当作当前产品能力说明。
