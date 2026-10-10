# ADR-009: v1 单机 Docker Compose 部署，按分层边界预留多租户 SaaS 迁移路径

## Status
Accepted (2026-10-09)

## Background
用户已拍板：**单机自部署优先，v1 用 Docker 一键起，不做多租户、不做账号体系**；但架构要**按可上云分层**，二期加多租户时不推倒重来。
候选部署：Docker Compose、Kubernetes/k3s、Podman Compose。

## Decision
1. **v1 用 Docker Compose（CLI 插件 v2 语法；Engine 28.x）**，默认 **2 个容器**：`db`（`pgvector/pgvector:pg18`）+ `api`（自建 python:3.12-slim，托管 `/api/v1/**` 与静态 SPA）；`ollama` 置于 profile `local-llm`（可选）。ComfyUI 走宿主机 `host.docker.internal:8188`。
2. 用户前置：Docker Desktop（WSL2）+ NVIDIA 驱动 ≥ 570；仅当要容器内跑 GPU 才需 NVIDIA Container Toolkit。
3. 数据卷：`pgdata`（DB，`pg_dump` 备份）、`assets`（素材/生成图）、`config`（配置与工作流模板）；另提供可移植导出 zip（含 `manifest.json` 声明 schema 版本）。
4. **留边界不实现**：所有内容行带 `owner_id`（默认 `'local'`）；鉴权走 `AuthProvider` 接口（v1 = no-op）；资产走 `AssetStore` 接口（v1 = 本地 FS）；LLM 走 `LLMProvider` 接口；检索走 `SearchProvider` 接口；合规走 `ModerationProvider` 接口。
5. **迁移动作（二期）**：启用 PG RLS 按 `owner_id/workspace_id` 隔离 → 替换 `AuthProvider` 为 JWT/OIDC → 换 `AssetStore` 为对象存储 → 换 `LLMProvider` 为云 API → compose 服务一一映射为 K8s Deployment（应用已无状态化）→ 按需引入 Meilisearch。
6. 否决 K8s/k3s（单机 MVP 严重过度设计）、Podman Compose（Windows + NVIDIA GPU 生态成熟度不足）。

## Consequences
- 正面：一键起、备份简单、上云只换实现不改业务。
- 负面：多一层接口抽象（可接受，是刻意的接缝）。
- 约束：no-op 鉴权仅在 v1 单机成立；暴露到公网前**必须先启用鉴权与合规钩子**（部署文档须显式警告）。

## Related ADRs
- ADR-004（数据库）
- ADR-006（本地推理）
