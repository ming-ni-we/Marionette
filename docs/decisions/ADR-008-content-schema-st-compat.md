# ADR-008: 内容 Schema 统一版本化，并以 SillyTavern V2 为兼容基线

## Status
Accepted (2026-10-09)

## Background
创作工作室与运行时引擎必须共用一套内容契约（角色卡/世界书/预设/会话状态），否则必然出现"各写一套"的漂移。同时，用户大概率要**导入酒馆（SillyTavern）卡**——其 Character Card V2 与世界书（Lorebook / `character_book`）是社区事实标准。
候选兼容策略：自定义 schema 全量自研；或"ST V2 超集"（沿用其字段名 + 平台扩展字段隔离）。

## Decision
1. **统一信封 + 版本号**：每类对象带 `spec` + `spec_version`（如 `rpg_card` / `1.0`），四类对象的字段级定义收敛到 `docs/spec/schemas.md`，作为**唯一权威契约**。
2. **铁律**：两侧只能读写这套 Schema；变更流程为"先改规格 → 升版本号 → 写迁移 → 再改代码"。
3. **ST V2 兼容基线**：角色卡的 `data` **沿用 ST V2 全部同名字段**（`name`/`description`/`personality`/`scenario`/`first_mes`/`mes_example`/`creator_notes`/`system_prompt`/`post_history_instructions`/`alternate_greetings`/`tags`/`creator`/`character_version`/`character_book`/`extensions`），平台自有字段全部隔离在 `data.extensions.rpg`。
4. **导入**：支持 V1/V2/V3 的 JSON/PNG(`chara` tEXt)/WEBP；V3 优先取 `ccv3`；无法识别的字段进 `extensions.st_unknown` **不销毁**；世界书做字段归一（`key`→`keys`、`disable`→`enabled` 取反、`order`→`insertion_order`）。
5. **导出**：平台卡可反向导出为 ST V2 JSON（可选 PNG 卡片）。
6. **未知字段保全**是硬规则（与 ST 规范一致），保证往返无损。

## Consequences
- 正面：导入酒馆卡近乎无损；两侧契约唯一、可演进、可审计；为广场/分享留数据余地。
- 负面：需维护转换层（`STCompatAdapter`）与其测试；平台扩展字段必须严守隔离在 `extensions`。
- 约束：读取方遇到更高 `spec_version` 必须拒绝写入并提示升级；破坏性变更须提供迁移脚本。

## Related ADRs
- ADR-001（前端类型由 OpenAPI 生成）
- ADR-004（JSONB 存储）
