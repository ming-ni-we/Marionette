# ADR-005: 中文全文索引用 PostgreSQL pg_trgm + pgvector（不引入 SQLite FTS5 / Meilisearch）

## Status
Accepted (2026-10-09)

## Background
需要中文全文检索（搜角色卡、世界书条目）。已知事实：
- SQLite FTS5 默认 `unicode61` 分词器把连续中文当**整段一个 token**，"数据库索引优化"整句才能命中，"索引"查不到；需 jieba 预分词 + 外部内容表 + 触发器同步（且与已选 PG 形成双库）。
- PostgreSQL 默认 FTS 对 CJK 亦需第三方分词器（`zhparser` / `pg_jieba`），需在镜像内编译扩展。
- Meilisearch 中文体验好、排序强，但为**独立服务**（+1 容器 + 索引同步），MVP 数据量下性价比低。
- MVP 数据量预期 < 10 万条卡片/条目。

## Decision
MVP 用 **PostgreSQL `pg_trgm`（三字组）GIN 索引 + `ILIKE`** 覆盖"子串/模糊"检索，**不引入分词器、不引入额外服务**；语义检索交给 pgvector。理由：
1. `pg_trgm` 对 CJK 按字符三字组建索引，**无需分词器**即可子串/模糊匹配，零额外依赖。
2. 与已选 PG 单库统一，无跨库同步。
3. 与 pgvector 形成"精确（trgm）+ 语义（vector）"互补双路（RAG 双存储思想）。
4. 明确二者**互补不互替**：trgm 命中"字面像"，vector 命中"意思像"。
5. 升级路径保留：数据量破 10 万或需要排序相关度时，引入 **Meilisearch 1.x**（或 PG `zhparser`/`pg_jieba`），通过增加索引服务 + 回填任务实现，业务代码不改（检索走 `SearchProvider` 接口）。

## Consequences
- 正面：零额外服务、零分词器部署负担、单库一致、上线快。
- 负面：`pg_trgm` 无排序相关度（BM25 类），只做过滤 + 简单排序；误召回率高于真分词。
- 约束：所有正文检索走 `SearchProvider` 接口，为后续换 Meilisearch 留缝。

## Related ADRs
- ADR-004（数据库）
