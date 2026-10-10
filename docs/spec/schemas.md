# 内容 Schema 契约（创作工作室 与 运行时引擎 的共享契约）

- 版本: v1.0 (Phase 1)
- 日期: 2026-10-09
- 作者: 高见远（首席架构师）
- 状态: 待团队评审

---

## 1. 铁律（BINDING RULES）

> **创作工作室与运行时引擎只能读写本文件定义的这套 Schema，不允许各写一套。**
> 任何一侧需要新字段，**先改本文件 + 升版本号 + 写迁移/兼容说明**，再改代码（spec-as-contract：先改规格再改代码）。

配套铁律：

1. **单一事实源**：Schema 的权威定义在数据库（JSONB 存储）与本文件；前端 TS 类型由 `openapi.yaml` 生成，不得手写平行类型。
2. **版本必填**：每个对象带 `spec` + `spec_version`。读取方遇到 `spec_version` 高于自己支持的最高版本时，**必须拒绝写入并提示升级**，不得静默丢字段。
3. **未知字段不销毁**：与 SillyTavern 规范一致的"向后兼容"约定——读取时保留未知字段（存入 `extensions`），保存时原样写回。
4. **禁 emoji 作功能图标**：Schema 中不存 emoji 作为"图标/功能标识"；`avatar` 类字段一律存资产 id，不存 emoji。
5. **字段命名**：JSON 层用 `snake_case`（与 ST V2 对齐，便于无损转换）；数据库列同名。
6. **时间**：一律 ISO-8601 UTC（`2026-10-09T12:00:00Z`）。
7. **ID**：一律 UUIDv4 字符串，平台自生成；外部导入对象的原始 id 存 `extensions.st_original_id`。

---

## 2. 总览：四类内容对象

| 对象 | spec | 版本 | 作用 | ST 对应 |
|---|---|---|---|---|
| 角色卡 Character Card | `rpg_card` | 1.0 | 角色人设 + 内嵌角色书 | SillyTavern Character Card V2 (`chara_card_v2`) |
| 世界书 World Book | `rpg_worldbook` | 1.0 | 关键词触发的知识条目集 | ST World Info / Lorebook / `character_book` |
| 预设 Preset | `rpg_preset` | 1.0 | 采样参数 + 提示词模板 + 预算 | ST 无直接等价（对应 ST 的 generation settings + prompt manager） |
| 会话状态 Session | `rpg_session` | 1.0 | 一场会话的完整运行态 | ST 无直接等价（ST 存 chat JSONL，本项目结构化） |

统一外层信封：

```json
{
  "spec": "<rpg_card | rpg_worldbook | rpg_preset | rpg_session>",
  "spec_version": "1.0",
  "id": "<uuid>",
  "data": { "...本文件定义的主体字段..." },
  "extensions": { "st_unknown": { "...导入时保留的未知字段..." } }
}
```

---

## 3. 角色卡 Schema (rpg_card v1.0)

### 3.1 设计原则

- `data` 中**沿用 SillyTavern V2 的全部同名字段**，使 ST 卡导入/导出近乎无损。
- 平台的扩展字段（头像、图集、默认预设、默认世界书等）**全部放 `data.extensions.rpg`**，不污染 ST 兼容层。

### 3.2 字段级定义

| 字段 | 类型 | 必填 | 默认 | 说明 | ST V2 对应 |
|---|---|---|---|---|---|
| `data.name` | string | 是 | — | 角色名 | `name` |
| `data.description` | string | 是 | `""` | 外貌/背景/设定主体 | `description` |
| `data.personality` | string | 否 | `""` | 性格关键词/摘要 | `personality` |
| `data.scenario` | string | 否 | `""` | 场景设定 | `scenario` |
| `data.first_mes` | string | 是 | — | 开场白 | `first_mes` |
| `data.mes_example` | string | 否 | `""` | 示例对话（含 `{{user}}:`/`{{char}}:`） | `mes_example` |
| `data.creator_notes` | string | 否 | `""` | 创作者备注（**不进 prompt**） | `creator_notes` |
| `data.system_prompt` | string | 否 | `""` | 覆盖全局系统提示（支持 `{{original}}`） | `system_prompt` |
| `data.post_history_instructions` | string | 否 | `""` | 历史后注入（jailbreak/指令，支持 `{{original}}`） | `post_history_instructions` |
| `data.alternate_greetings` | string[] | 否 | `[]` | 备用开场白（swipe） | `alternate_greetings` |
| `data.tags` | string[] | 否 | `[]` | 标签（仅筛选，不进 prompt） | `tags` |
| `data.creator` | string | 否 | `""` | 创作者名（不进 prompt） | `creator` |
| `data.character_version` | string | 否 | `""` | 卡片自身版本 | `character_version` |
| `data.character_book` | WorldBook \| null | 否 | `null` | 内嵌角色书（结构同 §4，但 spec 省略，直接为 book 主体） | `character_book` |
| `data.extensions.rpg` | object | 否 | `{}` | 平台扩展（见下） | — |

**`data.extensions.rpg` 子字段**

| 字段 | 类型 | 说明 |
|---|---|---|
| `avatar_asset_id` | string \| null | 头像资产 id（不存 emoji、不存外部 URL） |
| `gallery` | string[] | 图集资产 id 列表 |
| `default_preset_id` | string \| null | 默认预设 id |
| `default_worldbook_ids` | string[] | 默认挂载的世界书 id 列表 |
| `greeting_emotions` | object | 开场白 → 立绘/表情资产 id 映射（可选） |
| `visibility` | `"private" \| "unlisted" \| "public"` | 广场余量字段，v1 恒为 `private` |
| `owner_id` | string | 多租户余量字段，v1 恒为 `"local"` |
| `source` | object | 导入来源：`{ "format": "st_v2", "original_id": "...", "imported_at": "..." }` |

### 3.3 JSON Schema（等价形式）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://local/rpg/schemas/rpg_card-1.0.json",
  "title": "RPGCard",
  "type": "object",
  "required": ["spec", "spec_version", "data"],
  "properties": {
    "spec": { "const": "rpg_card" },
    "spec_version": { "const": "1.0" },
    "id": { "type": "string", "format": "uuid" },
    "data": {
      "type": "object",
      "required": ["name", "first_mes"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "description": { "type": "string", "default": "" },
        "personality": { "type": "string", "default": "" },
        "scenario": { "type": "string", "default": "" },
        "first_mes": { "type": "string" },
        "mes_example": { "type": "string", "default": "" },
        "creator_notes": { "type": "string", "default": "" },
        "system_prompt": { "type": "string", "default": "" },
        "post_history_instructions": { "type": "string", "default": "" },
        "alternate_greetings": { "type": "array", "items": { "type": "string" }, "default": [] },
        "tags": { "type": "array", "items": { "type": "string" }, "default": [] },
        "creator": { "type": "string", "default": "" },
        "character_version": { "type": "string", "default": "" },
        "character_book": { "$ref": "https://local/rpg/schemas/worldbook-1.0.json" },
        "extensions": { "type": "object", "default": {} }
      }
    },
    "extensions": { "type": "object", "default": {} }
  }
}
```

### 3.4 与 SillyTavern V2 的兼容与转换策略

**导入（ST V2 JSON / PNG / WEBP → 平台卡）**

1. **支持三种载体**：`.json`（裸 JSON）、`.png`（读 `tEXt` chunk，keyword = `chara`，base64 解码得 JSON）、`.webp`（同理）。
2. **V3 优先**：若 PNG 同时含 `chara`(V2) 与 `ccv3`(V3) 两个 tEXt chunk，**优先取 `ccv3`**；V3 的差异字段（如新 `assets`、`group_only_greetings`）在 v1 先落入 `extensions.st_unknown`，不丢。
3. **V1 兼容**：若 JSON 无 `spec` 字段（裸 6 字段），按 V1 解析，映射为 `data.{name,description,personality,scenario,first_mes,mes_example}`，其余补默认值。
4. **字段映射**：`chara_card_v2.data.*` → `rpg_card.data.*`（**同名字段一一映射**，无改名，无损）。
5. **`character_book`**：ST 的 `character_book` 主体直接映射为 §4 世界书主体（见 §4.4 兼容说明）。
6. **未知字段保全**：`data` 或 `character_book` 中平台不认识的键，全部收进 `extensions.st_unknown`，导出时原样写回。
7. **头像**：PNG/WEBP 原图存入 `AssetStore` → `avatar_asset_id`。

**导出（平台卡 → ST V2）**

- 反向映射 `data.*` → `chara_card_v2.data.*`；`extensions.rpg` 中的平台私有字段**不导出到 ST 兼容字段**（可选嵌入 `data.extensions.rpg`，ST 会作为未知字段保留）。
- 可选产出"PNG 卡片"：把 JSON base64 写入 PNG `tEXt`(key=`chara`)（以 ST 生态常用做法为例，示例非指定）。

**保真度承诺**

| 场景 | 承诺 |
|---|---|
| ST V2 → 平台 → ST V2 | 除平台新增字段外**逐字段一致**（含 `extensions` 未知键） |
| ST V1 → 平台 → ST V2 | 语义等价（V1 缺的字段补默认） |
| ST V3 → 平台 → ST V2 | 已识别字段一致；V3 独有字段落 `st_unknown` 保全 |

---

## 4. 世界书 Schema (rpg_worldbook v1.0)

### 4.1 顶层字段

| 字段 | 类型 | 必填 | 默认 | 说明 | ST 对应 |
|---|---|---|---|---|---|
| `data.name` | string | 否 | `""` | 世界书名 | `name` |
| `data.description` | string | 否 | `""` | 描述 | `description` |
| `data.scan_depth` | integer | 否 | `4` | 扫描最近多少条消息 | `scan_depth` |
| `data.token_budget` | integer | 否 | `1024` | 世界书段落 token 上限 | `token_budget` |
| `data.recursive_scanning` | boolean | 否 | `false` | 是否允许条目递归触发 | `recursive_scanning` |
| `data.max_recursion_depth` | integer | 否 | `3` | 递归深度硬上限（平台新增，防环） | — |
| `data.entries` | Entry[] | 是 | — | 条目列表 | `entries` |
| `data.extensions.rpg` | object | 否 | `{}` | `{ owner_id, visibility, tags[] }` | — |

### 4.2 条目 Entry 字段级定义

| 字段 | 类型 | 必填 | 默认 | 说明 | ST 对应 |
|---|---|---|---|---|---|
| `id` | string | 是 | 生成 | 条目 id。平台创建时生成 UUID 字符串；导入/调用方可传入自定义 id（ST 的 int id 会以 `extensions.st_original_id` 保真，见 `st_book.py`） | `id`(int) / `uid` |
| `keys` | string[] | 是 | `[]` | 主关键词 | `keys` / `key` |
| `secondary_keys` | string[] | 否 | `[]` | 次级关键词（`selective` 时需同时命中） | `secondary_keys` |
| `content` | string | 是 | `""` | 命中后注入的正文 | `content` |
| `comment` | string | 否 | `""` | 备注（**不进 prompt**，仅编辑器显示） | `comment` |
| `enabled` | boolean | 是 | `true` | 是否启用 | `enabled`/`disable`(取反) |
| `constant` | boolean | 否 | `false` | **常驻**：无条件注入（受预算约束） | `constant` |
| `selective` | boolean | 否 | `false` | 需 `keys` 与 `secondary_keys` 同时命中 | `selective` |
| `case_sensitive` | boolean | 否 | `false` | 大小写敏感 | `case_sensitive` |
| `match_whole_words` | boolean | 否 | `false` | 整词匹配（非子串） | `match_whole_words` |
| `use_regex` | boolean | 否 | `false` | **平台新增**：`keys` 按正则解释 | —（ST 部分分支支持） |
| `regex_flags` | string | 否 | `"i"` | 正则 flags（`i`/`m`/`s`） | — |
| `insertion_order` | integer | 是 | `100` | 插入顺序，**小者靠前** | `insertion_order` / `order` |
| `priority` | integer | 否 | `10` | **预算不足时的保留优先级，大者优先保留** | `priority` |
| `position` | enum | 否 | `"before_char"` | 插入位置（见下） | `position` |
| `depth` | integer | 否 | `4` | `at_depth` 时从末尾倒数第几条插入 | `depth` |
| `role` | enum | 否 | `"system"` | `at_depth` 注入角色：`system`/`user`/`assistant` | `role` |
| `vector_recall` | boolean | 否 | `false` | **平台新增**：除关键词外，允许按语义召回 | — |
| `vector_threshold` | number | 否 | `0.75` | 语义召回相似度阈值（0-1） | — |
| `token_count` | integer | 否 | 只读 | 服务端估算的 token 数（缓存，客户端不可写） | — |
| `extensions` | object | 否 | `{}` | 未知字段保全 | `extensions` |

**`position` 枚举**

| 值 | 语义 |
|---|---|
| `before_char` | 角色定义之前 |
| `after_char` | 角色定义之后 |
| `before_example` | 示例对话之前 |
| `after_example` | 示例对话之后 |
| `at_depth` | 历史中倒数 `depth` 条处插入（配合 `role`） |

### 4.3 触发语义（权威定义，运行时引擎必须按此实现）

1. 常驻条目（`constant=true`）无条件入选。
2. 否则对最近 `scan_depth` 条消息的拼接文本 `W`：
   - `use_regex=false`：`keys` 中任一为 `W` 的子串（`case_sensitive=false` 时忽略大小写；`match_whole_words=true` 时要求词边界）。
   - `use_regex=true`：以 `regex_flags` 编译每条 key，对 `W` 做 `search`（编译失败 → 降级为字面匹配并告警）。
   - `selective=true`：必须 `keys` 与 `secondary_keys` 各至少命中一条。
3. `vector_recall=true`：对 `W` 的 embedding 与条目 embedding 余弦相似度 ≥ `vector_threshold` 则入选。
4. `recursive_scanning=true`：新入选条目的 `content` 并入扫描文本，重复步骤 2，**深度不超过 `max_recursion_depth`**。
5. 排序：`insertion_order` 升序。
6. 预算裁决：累计 `token_count` 超过 `token_budget` 时，按 `priority` 降序保留，低 `priority` 先被丢弃。

### 4.4 与 SillyTavern 世界书 / `character_book` 的兼容

- **`character_book`（卡内嵌书）**：ST 的 `data.character_book` 主体结构 = 本 Schema `data`（去掉 spec 信封）。导入时整体映射；导出时反向映射。
- **关键词字段归一**：ST 历史上 `key`(string) 与 `keys`(string[]) 并存 → 统一读入 `keys`（字符串则包成单元素数组）。
- **`disable` ↔ `enabled`**：ST V2 可能用 `disable: true`；转换时 `enabled = !disable`。
- **`order` ↔ `insertion_order`**：同义，统一为 `insertion_order`。
- **未知字段**：条目级未知键收进该条目的 `extensions`；书级未知键收进书级 `extensions`。
- **优先级方向差异**：ST 的 `priority`（数字越小越先丢弃）与本 Schema 一致（**大者优先保留**）——导入时若来源用相反语义，转换层需取反，并在 `extensions` 记录 `priority_semantics_original`。

### 4.5 导入结果 `source_format` 枚举

导入接口（`POST /api/v1/import/card`、`POST /api/v1/import/worldbook`）返回的 `ImportResult.source_format`
用于标注实际解析成功的来源载体，取值与 `openapi.yaml` 的 `ImportResult` 枚举一致：

| 值 | 含义 |
|---|---|
| `st_v1` | SillyTavern 角色卡 V1（裸 6 字段 JSON） |
| `st_v2` | SillyTavern 角色卡 V2（`chara_card_v2` / PNG `chara` chunk） |
| `st_v3` | SillyTavern 角色卡 V3（PNG `ccv3` chunk） |
| `st_worldbook` | **SillyTavern World Info / lorebook JSON**（世界书导入；本轮契约补齐，此前枚举仅为角色卡设计而缺失该值） |
| `native` | 本平台原生信封（`rpg_card` / `rpg_worldbook`） |

---

## 5. 预设 Schema (rpg_preset v1.0)

### 5.1 字段级定义

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `data.name` | string | 是 | — | 预设名 |
| `data.description` | string | 否 | `""` | 描述 |
| `data.sampling` | object | 否 | 见下 | 采样参数 |
| `data.sampling.temperature` | number | 否 | `0.8` | 温度 |
| `data.sampling.top_p` | number | 否 | `0.95` | 核采样 |
| `data.sampling.top_k` | integer | 否 | `40` | Top-K |
| `data.sampling.min_p` | number | 否 | `0.05` | Min-P |
| `data.sampling.repetition_penalty` | number | 否 | `1.1` | 重复惩罚 |
| `data.sampling.frequency_penalty` | number | 否 | `0` | 频率惩罚 |
| `data.sampling.presence_penalty` | number | 否 | `0` | 存在惩罚 |
| `data.sampling.max_tokens` | integer | 否 | `1024` | 单次最大生成长度 |
| `data.sampling.seed` | integer | 否 | `-1` | 随机种子（-1 = 随机） |
| `data.sampling.stop` | string[] | 否 | `[]` | 停止序列 |
| `data.prompt_template.system` | string | 是 | — | 系统基座模板（含占位符） |
| `data.prompt_template.instruction` | string | 否 | `""` | 附加指令 |
| `data.prompt_template.chat_separator` | string | 否 | `"\n"` | 消息分隔 |
| `data.prompt_template.placeholders` | object | 否 | `{}` | 自定义占位符键值 |
| `data.context_budget` | object | 否 | 见下 | token 预算分配（详见架构 §4.6） |
| `data.context_budget.max_context_tokens` | integer | 否 | `8192` | 上下文窗口上限 |
| `data.context_budget.reserve_for_output` | integer | 否 | `1024` | 为输出预留 |
| `data.context_budget.character_pct` | integer | 否 | `15` | 角色定义占比 |
| `data.context_budget.world_info_pct` | integer | 否 | `25` | 世界书占比 |
| `data.context_budget.memory_pct` | integer | 否 | `15` | 长期记忆占比 |
| `data.context_budget.vector_recall_pct` | integer | 否 | `5` | 向量召回占比 |
| `data.context_budget.history_pct` | integer | 否 | `35` | 历史消息占比 |
| `data.memory` | object | 否 | 见下 | 记忆策略 |
| `data.memory.summarize_every_n_turns` | integer | 否 | `10` | 每 N 轮触发摘要 |
| `data.memory.summary_trigger_ratio` | number | 否 | `0.8` | 未摘要历史占用达历史预算该比例即触发 |
| `data.memory.vector_top_k` | integer | 否 | `5` | 向量召回条数 |
| `data.memory.extract_facts` | boolean | 否 | `true` | 是否抽取关键事实 |
| `data.image_hook` | object | 否 | 见下 | 出图钩子 |
| `data.image_hook.enabled` | boolean | 否 | `false` | 是否启用 |
| `data.image_hook.mode` | enum | 否 | `"manual"` | `manual`/`every_n_turns`/`on_scene_change` |
| `data.image_hook.every_n_turns` | integer | 否 | `10` | 配合 mode |
| `data.image_hook.workflow_template_id` | string | 否 | `null` | ComfyUI 工作流模板资产 id |
| `data.extensions.rpg` | object | 否 | `{}` | `{ owner_id, visibility }` |

### 5.2 占位符系统（提示词模板）

模板字符串中支持的占位符（组装时替换）：

| 占位符 | 含义 |
|---|---|
| `{{char}}` | 角色名 |
| `{{user}}` | 玩家名（会话级设置） |
| `{{persona}}` | 玩家设定文本 |
| `{{description}}` | 角色 description |
| `{{personality}}` | 角色 personality |
| `{{scenario}}` | 角色 scenario |
| `{{original}}` | 原全局系统提示（用于 `system_prompt`/`post_history_instructions` 覆盖语义） |
| `{{world_info}}` | 世界书命中块（由引擎注入，若模板未显式放置，则按默认顺序插入，见架构 §4.6） |
| `{{memory}}` | 长期记忆块 |
| `{{examples}}` | 示例对话 |
| `{{<custom_key>}}` | 来自 `prompt_template.placeholders` |

**规则**：未知占位符**原样保留**并记录告警（不静默吞掉）；替换是单遍的（占位符展开出的文本不再二次替换，防注入）。

### 5.3 与 SillyTavern 的对应

ST 无独立"预设"文件概念，其生成设置在 `settings.json` / 预设 JSON（community presets）中。转换策略：
- ST 生成参数（`temp`/`top_p`/`rep_pen`/`max_length` 等）→ `data.sampling.*`。
- ST Prompt Manager 的有序 prompt 列表 → 收敛为 `prompt_template.system` + 顺序由引擎按架构 §4.6 决定（**不逐条平移 ST 的 prompt 顺序**，因为本项目用统一定义的组装顺序；无法映射的条目收进 `extensions.st_prompt_items` 以备参考）。

---

## 6. 会话状态 Schema (rpg_session v1.0)

### 6.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `data.character_card_id` | string(uuid) | 是 | 绑定的角色卡 |
| `data.preset_id` | string(uuid) | 是 | 使用的预设 |
| `data.worldbook_ids` | string[] | 否 | 挂载的世界书（可含卡内书） |
| `data.user_persona` | object | 否 | `{ name, description }` |
| `data.status` | enum | 是 | `active` / `paused` / `archived` |
| `data.state_machine` | object | 是 | 见 6.2 |
| `data.scene` | object | 否 | 见 6.3 |
| `data.messages` | Message[] | 是 | 消息流，见 6.4 |
| `data.triggered_entries` | object | 否 | `{ "<entry_id>": { "count": int, "last_turn": int } }` |
| `data.memory` | object | 否 | 见 6.5 |
| `data.context` | object | 否 | `{ last_assembled_at, last_prompt_tokens, last_estimate_actual_delta }` |
| `data.extensions.rpg` | object | 否 | `{ owner_id }` |

### 6.2 状态机 `state_machine`

| 字段 | 类型 | 说明 |
|---|---|---|
| `current` | enum | `idle` / `assembling` / `generating` / `post_processing` / `interrupted` / `error` |
| `turn` | integer | 已完成轮次 |
| `last_error` | object\|null | `{ code, message, at }` |
| `version` | integer | 乐观锁版本号（防并发双击） |

**合法迁移**（非法迁移必须被拒绝）：

```
idle        -> assembling
assembling  -> generating | error
generating  -> post_processing | interrupted | error
post_processing -> idle | error
interrupted -> idle (经重新生成/swipe)
error       -> idle (经 reset)
```

### 6.3 场景 `scene`

| 字段 | 类型 | 说明 |
|---|---|---|
| `location` | string | 当前位置 |
| `time` | string | 剧情内时间 |
| `mood` | string | 氛围 |
| `summary` | string | 当前场景摘要 |
| `bg_asset_id` | string\|null | 背景图资产 id |

### 6.4 消息 `messages[]`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string(uuid) | 是 | 消息 id |
| `role` | enum | 是 | `user` / `assistant` / `system` / `tool` |
| `content` | string | 是 | 正文 |
| `status` | enum | 是 | `streaming` / `complete` / `incomplete` |
| `created_at` | string(datetime) | 是 | ISO-8601 |
| `token_count` | integer | 否 | token 数（服务端估算） |
| `meta` | object | 否 | 见下 |

**`meta` 子字段**

| 字段 | 类型 | 说明 |
|---|---|---|
| `swipe_index` | integer | 该位置的第几版（重新生成） |
| `swipe_group_id` | string | 同一位置的多个 swipe 共享的组 id |
| `greeting_index` | integer\|null | 若为开场白，对应第几个 greeting（-1 = first_mes） |
| `triggered_entry_ids` | string[] | 生成该条 assistant 消息时命中的世界书条目 |
| `image_asset_id` | string\|null | 该消息附带的生成图 |
| `parent_id` | string\|null | 重新生成时指向被替代的旧消息 |

### 6.5 记忆 `memory`

| 字段 | 类型 | 说明 |
|---|---|---|
| `rolling_summary` | string | 滚动摘要（段 A） |
| `summary_upto_message_id` | string\|null | 摘要已覆盖到哪条消息（其之前的不再进历史窗口） |
| `facts` | Fact[] | 关键事实（段 B） |

**Fact**

| 字段 | 类型 | 说明 |
|---|---|---|
| `key` | string | 事实键，如 `玩家姓名` |
| `value` | string | 事实值 |
| `confidence` | number | 置信度 0-1 |
| `source_message_id` | string\|null | 来源消息 |
| `updated_at` | string(datetime) | 更新时间 |

> 段 C（向量召回）不持久化在 session 内，每轮从 `content_embeddings` 动态查询（见架构 §4.5）。

> **P0 实现口径提示（与 PRD F14 裁定一致）**：MVP 的"向量检索/RAG 记忆"为 P1，默认关闭。P0 记忆 = 自动摘要（`rolling_summary`）+ 关键事实（`facts`）+ 世界书关键词触发。Schema 里保留向量相关字段（`worldbook.entries[].vector_recall` / `preset.memory.vector_top_k` / `content_embeddings` 表）**仅作数据下余地**，运行时默认不启用，二期开启时无需改 Schema。

### 6.6 会话状态机 / 中断恢复（与字段对应）

- 每次生成：`state_machine.current` 按 §6.2 迁移；`version` 自增（乐观锁）。
- 流式检查点：assistant 消息以 `status='streaming'` 落库，周期性 upsert 已生成文本；结束转 `complete`，中断转 `incomplete`。
- 服务重启回收：启动时把所有 `streaming` 改 `incomplete`，相关 session 状态回 `idle`。
- 恢复 = 对该位置再次生成（swipe）：新建消息 `parent_id` 指向旧消息，旧消息保留（不删）。

---

## 7. 版本演进与迁移规则

1. **向后兼容优先**：新增字段必须可选 + 有默认值；重命名/删除字段属破坏性变更，须升 `spec_version` 主/次版本。
2. **读取兼容**：读取方支持"当前 + 前一个次版本"；遇到更高版本拒绝写入。
3. **迁移脚本**：破坏性变更须提供一次性迁移（Alembic 迁移 + 内容重写任务），迁移前后各存一份备份。
4. **导出锚定**：任何导出物（卡片/世界书/预设/会话档案）的 `manifest.json` 必须写明各对象 `spec` + `spec_version`，导入方据此选择解析路径。
5. **未知字段保全**：所有层级（信封 / data / entry / extensions）的未知字段都不得销毁（与 ST 规范一致）。

---

## 8. 使用铁律汇总（给前后端与运行时引擎的硬约束）

1. 读写内容对象**只走本 Schema**；不得在任一侧私建平行结构。
2. 前端 TS 类型由 `openapi.yaml` 生成，**禁止手写**与 Schema 冲突的类型。
3. 组装 prompt 时，段落顺序与预算分配必须遵循 §5.1 与架构 §4.6；未知占位符原样保留 + 告警，不静默丢弃。
4. `token_count` / `state_machine.version` 等**只读字段**，客户端不得直写。
5. 任何 Schema 变更：**先改本文件 → 升版本号 → 写迁移 → 再改代码**（spec-as-contract）。

---

## 9. 检索/筛选字段契约（P0，与 `openapi.yaml` 的 `SearchQuery` 对齐）

> 依据架构 §9.4（OPEN-006 裁决）：内容库搜索/筛选进 P0，走 `pg_trgm` + `ILIKE`（ADR-005）。
> 所有 list 端点复用同一套参数命名与语义，**禁止前端各写一套 query 名**。

**统一查询参数（`components.parameters` 可复用组件）**

| 参数 | 类型 | 语义 | 对应可检索字段 |
|---|---|---|---|
| `q` | string(≤200) | 关键词，pg_trgm 三字组 + ILIKE，多词 AND | 见下表 |
| `tags` | string[] | 标签多值（AND） | `data.tags`（卡）/ `data.extensions.rpg.tags`（世界书） |
| `sort` | enum | `created_at` / `updated_at` / `name` / `last_message_at` | — |
| `order` | enum | `asc` / `desc`（默认 `desc`） | — |
| `status` | enum | `active` / `paused` / `archived`（**仅会话列表**） | `data.status` |
| `page` / `limit` | integer | 分页（page≥1，1≤limit≤100，默认 20） | — |

**各资源的 `q` 检索字段**

| 端点 | `q` 命中字段 |
|---|---|
| `GET /api/v1/cards` | `data.name`、`data.description`、`data.personality`、`data.scenario`、`data.tags` |
| `GET /api/v1/worldbooks` | `data.name`、`data.description`、`data.entries[].keys`、`data.entries[].content`、`data.entries[].comment` |
| `GET /api/v1/presets` | `data.name`、`data.description` |
| `GET /api/v1/sessions` | `data.scene.location`、`data.scene.summary`（会话记录不检索消息正文，消息全文检索归 v2/F15） |

**错误语义**：`sort`/`order`/`status` 非法值、`limit` 越界、`q` 超长 → **400（错误码 4000）**，见 `components.responses.BadRequest`。

**与 `/worldbooks/{id}/test` 的口径一致性**：`test` 端点用于**条目级触发模拟**（判断"为何没触发"，输入 `sample_text`，输出逐条命中/预算裁决）；list 的 `q` 用于**资源检索**（找到某本书）。二者都是关键词/子串语义，**共用同一文本匹配基元**（`case_sensitive` 与 `match_whole_words` 由条目自身控制），但用途不同，不互相替代。

---

## 10. 资产 Schema（支持实体：rpg_asset，非四类内容对象之一）

> 资产（头像/图集/背景/生成图）是可被内容对象与运行时共同引用的支持实体。它不参与"创作工作室 ↔ 运行时引擎"的 Prompt 组装契约，但被 `card.data.extensions.rpg.avatar_asset_id` / `gallery` / `message.meta.image_asset_id` / `session.scene.bg_asset_id` 引用。
> 归属：资产**要么归属角色（`card_id`），要么归属会话（`session_id`）**，可都为空（游离资产）。

### 10.1 字段级定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string(uuid) | 是 | 资产 id |
| `kind` | enum | 是 | `avatar` / `gallery` / `background` / `generated` |
| `filename` | string | 是 | 原始文件名 |
| `content_type` | string | 是 | MIME 类型 |
| `size_bytes` | integer | 是 | 字节数 |
| `card_id` | string(uuid)\|null | 否 | 归属角色（"以角色为中心"的资产库主键） |
| `session_id` | string(uuid)\|null | 否 | 归属会话（出图/快照来源） |
| `message_id` | string(uuid)\|null | 否 | 关联消息（出图对话位置） |
| `tags` | string[] | 否 | 标签（供资产库筛选） |
| `meta` | object | 否 | 生成图额外信息（`prompt`/`seed`/`workflow`/`width`/`height` 等） |
| `created_at` | string(datetime) | 是 | ISO-8601 |

### 10.2 出图自动归档链路（PRD P0："出图自动归档到当前角色图集"）

契约落点，全链路必须闭合：

1. 前端/钩子调 `POST /api/v1/images/jobs`，带 `card_id`（或 `session_id`，由会话推导 `card_id`）。
2. 任务完成（`status=done`）时，服务端**自动创建 `kind=generated` 的 Asset**：写入 `card_id`/`session_id`/`message_id`/`meta`，返回 `asset_id`，并置 `ImageJob.archived=true`。
3. 若指定 `card_id`，同时把该资产登记进该角色的图集（即 `card.data.extensions.rpg.gallery` 可检索到）。
4. 前端据 `asset_id` 用 `GET /api/v1/assets/{id}/content` 取图；资产库页用 `GET /api/v1/assets?card_id=...` 或便捷端点 `GET /api/v1/cards/{cardId}/assets` 列表。

> 铁律：**归档由服务端自动完成，前端不得自行拼装资产记录**（避免出现"图在文件夹里但资产库查不到"的脱节，正是 PRD 空白 #5 要消除的问题）。

### 10.3 资产检索参数（P0，对应 PRD F16）

| 参数 | 语义 |
|---|---|
| `q` | 关键词（匹配 `filename`、`tags`、`meta.prompt`） |
| `tags` | 标签多值（AND） |
| `card_id` / `session_id` | 归属过滤 |
| `kind` | 类型过滤 |
| `sort` / `order` / `page` / `limit` | 同 §9 统一约定（`sort` 支持 `created_at`/`updated_at`/`name`） |
