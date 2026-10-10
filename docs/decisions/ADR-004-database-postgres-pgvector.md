# ADR-004: 数据库采用 PostgreSQL 18 + pgvector 0.8.6

## Status
Accepted (2026-10-09)

## Background
需要同时承载：关系数据（内容元数据、会话、消息）、半结构化数据（卡片/世界书的 JSONB）、**向量检索**（记忆语义召回）、**中文模糊全文检索**。且架构要求"分层可上云、二期加多租户不推倒重来"。
候选：PostgreSQL + pgvector、SQLite、MongoDB。

## Decision
选择 **PostgreSQL 18.6 + pgvector 0.8.6**（镜像 `pgvector/pgvector:pg18`）。理由：
1. **一个库覆盖四类需求**：关系 + JSONB + 向量(pgvector) + 模糊检索(pg_trgm)，减少服务数与运维面。
2. 事务一致：会话、消息、触发记录、向量同库，无跨存储一致性问题。
3. 迁移路径最直接：二期多租户可用 PG RLS；横向扩展生态成熟。
4. 锚定 pgvector `0.8.6`（`0.8.2` 已修复 HNSW 并行构建的 CVE）。
5. 否决 SQLite（并发写弱、无 pgvector 等价物、上云需重写）、MongoDB（向量/关系能力弱于 PG，引入新范式）。

## Consequences
- 正面：单库多能、事务一致、上云平滑。
- 负面：单机多一个容器（可接受）；JSONB 复杂查询需谨慎建索引。
- 约束：向量列维度需与 embedding 模型一致（bge-large-zh = 1024）；HNSW 索引在数据量增长后需调参（`m`/`ef_construction`）。

## Related ADRs
- ADR-005（全文索引方案）
- ADR-009（部署与迁移边界）
