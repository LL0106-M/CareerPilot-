# CareerPilot 本地开源模型部署设计

日期：2026-11-03

## 意图

将 CareerPilot 的主模型从付费的阿里云 Qwen 接口切换为可在当前 Windows 电脑上通过 CPU 运行的开源模型，保留 OpenAI-compatible 调用边界，使未来迁移到云端 GPU 时无需重写 Agent。

## 目标

- 使用 `Qwen3-4B GGUF Q4_K_M` 作为首个本地模型。
- 使用官方 `llama.cpp` server Docker 镜像提供 OpenAI-compatible API。
- 在现有 Compose 中同时编排 CareerPilot 与模型服务。
- 模型只绑定本机测试端口，模型缓存持久化，重启不重复下载。
- 开发环境不依赖付费模型、DashScope 搜索或 MemOS Cloud。
- 保留未来本地/云端双模型路由的接口兼容性。

## 非目标

- 本轮不部署 Qwen3-32B、DeepSeek-V3 或云端 GPU。
- 本轮不实现完整 MCP Client、MCP 权限策略或联网搜索服务。
- 本轮不要求 4B 模型独立承担高风险写操作或复杂多工具规划。
- 不覆盖用户当前工作区中的其他未提交改动。

## 约束与风险

- 当前系统能看到 8 个逻辑处理器，但内存信息因系统权限无法读取；首次配置按保守参数运行。
- 当前环境没有可用的 `docker` 命令，代码与配置完成后仍需用户安装并启动 Docker Desktop。
- CareerPilot 当前 Compose 已占用宿主机 `8080`，模型测试端口使用 `127.0.0.1:8081`。
- CPU 推理速度有限，首版上下文限制为 4096，并发限制为 1。
- 生产配置当前会校验 API key；本地 llama.cpp 不验证 key，但 CareerPilot 仍提供非敏感占位值以满足客户端和配置契约。

## 考虑过的方案

### A. llama.cpp + Docker Compose（选定）

优点是完全开源、GGUF CPU 推理成熟、参数可控，并可直接复用项目现有的 OpenAI-compatible 模型客户端。模型与应用由同一 Compose 编排，未来替换为云端 vLLM 只需要调整模型地址和名称。

### B. Ollama

Windows 上安装和运行更简单，但它形成项目之外的独立运行时，版本、模型和启动参数不如 Compose 容易复现，因此不作为项目默认部署方式。

### C. Windows 原生 llama.cpp

可能减少 Docker/WSL2 的少量开销，但需要手动管理二进制、模型文件和启动过程，不利于后续部署和交付。

## 运行结构

```text
CareerPilot container
  -> http://local-llm:8080/v1
     -> llama.cpp server
        -> Qwen3-4B GGUF Q4_K_M

Windows host
  -> http://127.0.0.1:8081/v1  # 仅用于健康检查与调试
```

Compose 使用独立命名卷保存 Hugging Face/llama.cpp 模型缓存。模型服务先通过健康检查，CareerPilot 再启动。模型端口只绑定 `127.0.0.1`，不暴露给局域网或公网。

## 配置行为

- Compose 内：`CAREERPILOT_MODEL_BASE_URL=http://local-llm:8080/v1`
- 模型名：使用 llama.cpp `/v1/models` 暴露的本地模型标识。
- API key：本地非敏感占位值，不用于鉴权。
- 不设置 DashScope 凭证时，现有付费联网搜索保持关闭。
- 不设置 MemOS Cloud key 时，本地统一记忆继续作为权威存储。
- Embedding 保持当前可选策略；本轮不把生成模型同时当作 embedding 模型。

## 联网搜索的后续 MCP 设计

联网查询从模型提供商解耦，后续通过 CareerPilot MCP Client 接入独立搜索工具：

```text
Qwen3-4B / 云端模型
  -> CareerPilot Tool Registry
     -> MCP Client Adapter
        -> Search MCP Server
           -> 自托管 SearXNG
```

建议暴露最小只读工具集：`search_web` 和 `fetch_page`。结果必须包含 URL、标题、摘要、时间与来源；CareerPilot 负责查询改写、去重、重排、缓存、引用审计和提示词注入隔离。搜索请求不得包含完整简历、邮箱、电话等个人敏感信息。

SearXNG 是免费开源的元搜索服务，但仍会访问上游搜索引擎，并可能受到限流或验证码影响。MCP 负责工具协议和隔离，不负责建立互联网索引。

## 验收标准

- Compose 配置可通过静态解析。
- 模型服务有持久化缓存、localhost 端口绑定和健康检查。
- CareerPilot 在 Compose 网络内指向 `local-llm`，不再要求付费模型地址。
- 单元测试覆盖本地模型配置，现有相关测试不回归。
- Docker 可用后，`/health`、`/v1/models` 和 `/v1/chat/completions` 可完成冒烟验证。
- 文档明确首次下载、启动、停止、日志、健康检查和资源调优方式。

