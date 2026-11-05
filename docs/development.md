# 本地开发与部署

本页集中维护运行、部署与 MCP 配置。产品说明见 [产品指南](product/README.md)，系统原理见 [技术架构](architecture/README.md)。

## 1. 环境要求

- Docker Desktop，并支持 `docker compose`；
- 首次启动可下载约 2.5 GB 的模型权重和所需镜像；
- 至少 8 GB 内存，建议 16 GB；
- 完整部署需在 `.env.production` 配置 Cookie、邮件验证等应用设置。

本地模型默认使用 `Qwen3-4B GGUF Q4_K_M`，由 `llama.cpp` 在 CPU 上运行，不需要付费模型 API。

## 2. 启动本地模型

```powershell
docker version
docker compose version

docker compose up -d local-llm
docker compose logs -f local-llm
```

模型加载完成后可按 `Ctrl+C` 退出日志查看，容器仍会继续运行。调试接口只绑定本机：`http://127.0.0.1:8081/v1`。

```powershell
.venv\Scripts\python.exe scripts\smoke_local_model.py
```

模型权重保存在 `local-llm-cache` 命名卷中，普通停止和重启不会重复下载：

```powershell
docker compose stop local-llm
docker compose start local-llm
```

## 3. 启动完整服务

```powershell
docker compose up -d
.venv\Scripts\python.exe scripts\smoke_deployment.py --base-url http://127.0.0.1:8080
```

```powershell
docker compose ps
docker compose down
```

当前保守配置使用 4096 上下文和单请求并发。确认内存余量和推理速度后再提高 `compose.yaml` 中的 `-c` 或 `-np`。不要把 `8081` 改为公网绑定：llama.cpp 本地接口默认不提供应用级鉴权。

## 4. 配置 MCP 工具服务器（可选）

Tool calling 是模型请求调用工具的方式；MCP 是发现和连接外部工具服务器的标准协议。CareerPilot 的 Runtime 仍掌控模型—工具循环，MCP 只提供可插拔工具。

```powershell
Copy-Item config\mcp.servers.example.json config\mcp.servers.json
$env:CAREERPILOT_MCP_CONFIG_PATH = "config/mcp.servers.json"
.venv\Scripts\python.exe scripts\inspect_mcp_tools.py --config config\mcp.servers.json
```

支持两种连接方式：

- `stdio`：在本机启动 MCP 子进程，适合访问本地简历、SQLite 记录或本地搜索服务；只传入配置中明确声明的环境变量。
- `streamable_http`：连接已经运行的 MCP HTTP 服务；非本机地址必须使用 HTTPS，本机 `127.0.0.1` / `localhost` 可使用 HTTP。

安全默认值是“不暴露”：工具必须标记 `readOnlyHint=true` 且不能标记 `destructiveHint=true`；建议再用 `allowed_tools` 配置白名单。未标注风险、写入型、破坏性或指纹过期的工具会被拒绝。每轮最多选择 8 个相关工具，返回内容会限长并标记为不可信数据。

`inspect_mcp_tools.py` 只读取工具描述，不调用工具。当前示例只预留搜索连接位，不会自动部署 SearXNG 或其他搜索引擎。

详细策略见 [MCP Tool Platform Design](superpowers/specs/2026-11-03-mcp-tool-platform-design.md)。
