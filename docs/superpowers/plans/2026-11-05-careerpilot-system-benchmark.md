# CareerPilot System Benchmark Implementation Plan

**Goal:** 建立可重复运行的 CareerPilot RAG 与记忆系统冻结基准，并生成机器可读和人工可读报告。

**Architecture:** 评测器直接调用生产 RAG、Memory 组件；每个 Case 使用独立 SQLite 数据库；两套系统分别汇总指标，安全硬失败单列。

**Tech Stack:** Python、pytest、SQLite、JSON、Markdown。

## Implementation tasks

1. 用测试固定检索指标、系统隔离、敏感记忆边界和报告结构。
2. 建立 8 条 RAG 冻结 Case，并实现独立运行与指标计算。
3. 建立 10 条记忆冻结 Case，并实现召回、写入门控、纠正和去重评测。
4. 提供命令行入口，输出 JSON 与 Markdown 基线报告。
5. 运行聚焦测试、代码规范检查和完整测试套件，记录真实失败而非调整期望值。
