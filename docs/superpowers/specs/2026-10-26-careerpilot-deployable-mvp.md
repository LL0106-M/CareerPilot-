# CareerPilot 可部署 MVP 规格

## 目标

CareerPilot 必须能以一个生产进程提供 React SPA 与 FastAPI API，使用同源 Cookie，持久数据全部落在可挂载目录，并在错误配置时启动失败而不是带着开发默认值上线。

## 部署形态

- Node 22 仅在镜像构建阶段执行 `npm ci && npm run build`。
- Python 3.12 运行 FastAPI，并托管构建后的 `frontend/dist`。
- 单实例、单 worker；SQLite 数据目录挂载到 `/app/data`。
- 容器以非 root 用户运行，提供 liveness `/health` 与 readiness `/ready`。
- 前端和 API 同源；生产环境不依赖 Vite proxy。

## 生产门禁

- `CAREERPILOT_ENVIRONMENT=production` 时禁止默认 Cookie secret、占位模型密钥和缺失的前端构建目录。
- Cookie 使用 `Secure`、`HttpOnly`、`SameSite=Lax`。
- 用户上传设硬性字节上限，超限返回 413。
- 未匹配的 `/v1/*` 必须保持 404，不能被 SPA fallback 吞掉。
- 部署文档必须明确：当前是匿名 Cookie 隔离的单机 MVP，不等于正式账号体系；公开多租户上线仍需 OAuth/login、token vault、备份与迁移方案。

## 验收

1. 前端生产构建、Python 测试、类型检查通过。
2. 以 production 环境变量启动服务后，`/health`、`/ready`、`/`、`/chat` 返回正确内容，未知 `/v1/*` 返回 404。
3. CI 能构建容器镜像；Compose 声明持久卷与健康检查。
