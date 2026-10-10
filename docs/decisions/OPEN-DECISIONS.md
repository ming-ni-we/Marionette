# OPEN-DECISIONS — 悬而未决登记册

> 项目：**提线 (Marionette)** — AI 角色扮演平台（创作工作室 + 运行时引擎）
> 规则：只追加 + 就地关闭（OPEN → RESOLVED，补 Resolution 字段）。每次 Phase 开始时复现未决项到工作上下文最前面。
> 三类固定 slug：`waiting-on-external-condition` / `design-decision-to-evaluate` / `existing-design-boundary`

**汇总：0 未决 + 9 已决**

| 编号 | Date | Source | 类别 (slug) | Open Item | Related Constraints | Current Leaning | Blocked By | Status | Resolution |
|---|---|---|---|---|---|---|---|---|---|
| OPEN-001 | 2026-10-09 | Phase 0 | waiting-on-external-condition | 「面向国内用户」与「单机自部署优先」的形态张力：v1 是否内建完整内容安全审核中间件 | 内容合规要求 vs 交付速度 | v1 只做可插拔审核接口 + 基础敏感词过滤 | — | **RESOLVED** (2026-10-09) | v1 = 基础词表过滤 + **可插拔 + 可关闭**，成本 1-2 人日（ADR-011）。PM 补强：审核层必须可关闭，否则劝退创作者。**用户后续决定仅限自用后，合规压力进一步下降**（不面向公众 → 不触发大模型备案/登记） |
| OPEN-002 | 2026-10-09 | Phase 0 | design-decision-to-evaluate | LLM 接入策略：国内合规云端 API / 本地推理 / 混合适配层 | 合规 + 显存 16GB + 推理成本 | 统一 OpenAI 兼容适配层 | — | **RESOLVED** (2026-10-09) | 自研 OpenAI 兼容薄层；锁定 7 类 `error_class`（ADR-006 + ADR-010）。**⚠️ 已被 2026-10-09 形态变更部分覆盖**：云端部署后默认后端从「本机 Ollama 自动探测」改为「云端 API（BYOK）」，Ollama 降为可选后端（仅当服务端能访问到 GPU 时）。见 OPEN-009 |
| OPEN-003 | 2026-10-09 | Phase 0 | waiting-on-external-condition | 首个可玩垂直切片的题材/角色范围未定（影响首屏示例卡与编辑器字段权重） | MVP 范围 vs schema 通用性 | 用「现代日常向」通用角色卡验证 schema | — | **RESOLVED** (2026-10-09, 用户拍板) | **用户决定：用「现代日常向」通用角色卡验证 schema**。范围锁定「日常/现代都市」语境 3–5 张示例卡，不绑死单一题材。**编辑器字段权重据此定为**：`description`/`personality`/`scenario`/`first_mes`/`mes_example` 前置（日常向靠稳定人设 + 长期关系推进），世界观类与 `character_book` 后置（渐进披露） |
| OPEN-004 | 2026-10-09 | Phase 0 | design-decision-to-evaluate | 内容 schema 是否兼容 SillyTavern 卡片格式 | 生态导入成本 vs 自有演进自由度 | v1 支持**导入** ST 卡片 | — | **RESOLVED** (2026-10-09) | 卡 `data` 沿用 ST V2 同名字段，平台字段隔离在 `extensions.rpg`；支持 V1/V2/V3 的 JSON/PNG/WEBP 导入，**可回导 ST V2**（ADR-008）。「一张卡绑定多本世界书 + 完整导出」为 P0 差异化承诺 |
| OPEN-005 | 2026-10-09 | Phase 1 (PM) | waiting-on-external-condition | 产品定名：「窑」(Kiln) /「提线」(Marionette) /「台本」(Script) | 定名影响域名/包名/UI 文案/Docker 镜像名 | 未定，等用户拍板 | — | **RESOLVED** (2026-10-09, 用户拍板) | **用户选定：「提线」（英文名 Marionette）**。命名理由：创作者掌线、AI 登台，「线」隐喻世界书/预设对运行的驱动，且暗含「数据与资产在你手里」的掌控感。命名落地：镜像/包名前缀 `marionette-`、UI 文案「提线」、仓库目录 `marionette/`。⚠️ 仅自用阶段不做商标检索，正式对外前需补 |
| OPEN-006 | 2026-10-09 | Phase 1 (设计师提请) | design-decision-to-evaluate | 会话历史与内容库的「搜索 + 筛选」是否纳入 v1 P0 | 存储层已含全文索引；前端筛选 UI 额外工作量 | 内容库搜索/筛选进 P0 | — | **RESOLVED** (2026-10-09) | 内容库（卡/世界书/预设/图集）**搜索 + 筛选进 P0**（pg_trgm + ILIKE，<1 人日，ADR-005）；**跨会话全文检索 F15 归 v2**。门禁第 1 次打回 → 架构师补 11 个参数组件并挂 4 个 list 端点；PM 同步新增 **F16**（RICE 9.00，P0） |
| OPEN-007 | 2026-10-09 | Phase 1 (门禁发现) | design-decision-to-evaluate | **图集（assets）无列表端点，导致 P0 的「以角色为中心的资产库」与设计师的「角色图集页」无数据来源** | PRD F16 要求搜索覆盖图集；PM 市场空白 #5 = 图集与运行时脱节；`/api/v1/assets` 仅 POST，无 GET | 方案 A：新增 `GET /api/v1/assets` | — | **RESOLVED** (2026-10-09) | **A + B 都做**。A：`GET /api/v1/assets`（9 参数含 `card_id`/`session_id`/`kind`，返回 `PagedAssets`）；B：`GET /api/v1/cards/{cardId}/assets`。扩展 `Asset`（+`card_id`/`session_id`/`message_id`/`tags`/`meta`）。**归档链路契约化**：`ImageJob` 完成时服务端自动创建 `kind=generated` 资产并登记进角色图集，前端禁止自行拼装。复验 34 path / 50 op / 43 schema / 14 param，`$ref` 零缺失 |
| OPEN-008 | 2026-10-09 | 用户提问（发行形态） | waiting-on-external-condition | 发行形态是否从「单机自部署工具」变更为「Steam 商店发行的商业产品」 | 版号：Steam 全球区不需要中国游戏版号（实务定性为跨境数字贸易；「Steam 中国/蒸汽平台」则需要）。生成式 AI 三轨制：算法备案（并行必办）+ 大模型登记（调已备案 API，1–3 月）或大模型备案（自研/微调，6–8 月）。关键分界：对模型输出做二次处理可能被认定「实质性修改」→ 登记升级为备案。《标识办法》(2025-09-01 施行) 第 7 条要求分发平台上架核验标识材料 | v1 形态不变 | — | **RESOLVED** (2026-10-09, 用户拍板) | **用户决定：暂不考虑对外开放，仅限自用**。→ 不进入商店发行流程，版号议题**不适用**；因不面向境内公众提供服务，**通常无需**大模型备案/登记（建议正式运营前与属地网信办确认算法备案口径）。**残留风险**：一旦云端实例被不特定人访问到，「自用」在事实上会变成「面向公众」，故必须做访问控制（见 OPEN-009） |
| OPEN-009 | 2026-10-09 | 用户形态变更（云端自用） | design-decision-to-evaluate | **云端部署下「图像生成钩子」与「本地推理」如何落地**：云端服务器无用户本机的 RTX 5060Ti 与 ComfyUI，原设计「探测本机 ComfyUI 127.0.0.1:8188」在云端失效 | 架构 §5.3 已预留 `ImageProvider` / `LLMProvider` 可替换接缝（换实现不动业务代码）；云 GPU 按量计费成本高 | 倾向：v1 出图改走本机 ComfyUI 反连或降级 P1 | — | 用户拍板 | **RESOLVED** (2026-10-09, 用户拍板) | **用户选定方案 C：云端图像 API（BYOK）**。`ImageProvider` = `CloudImageProvider`（OpenAI 兼容 images 接口或国内图像 API），仅需配置切换；`LocalComfyUIProvider` 代码保留但 **v1 默认关闭**。**收益**：零 GPU 运维、按量付费、与运行时同域无跨网链路。**代价**：工作流可控度低于自建 ComfyUI，角色立绘跨图一致性需靠 prompt 与参考图策略补偿（记入 Phase 3 风险）。**云服务器采购**：腾讯云轻量应用服务器 · 2核4G · 境外（中国香港）地域 · Ubuntu 22.04 · 包年 |

## 2026-10-09 用户形态变更（Phase 1 之后，重要）

> 用户在原「单机自部署」基础上给出四项决定，构成对 Phase 1 三文档的**形态级变更**：

1. **不对外开放，仅限自用** → 不发行、不面向公众 → 合规压力大幅下降（备案/登记通常不适用）
2. **部署到云端**（而非单机本机） → 需要访问控制、HTTPS、备份、服务器成本
3. **平台命名「提线」（Marionette）**
4. **用「现代日常向」通用角色卡验证 schema**

**架构影响评估（已核实 `docs/02-architecture.md` §5.3）**：架构在设计时已预留适配层接缝（`AuthProvider` / `AssetStore` / `LLMProvider` / `ImageProvider` / `ModerationProvider`），原话是「v1 就把这些缝留出来，二期只换实现，不动业务代码」。**因此本次形态变更不需要推倒重来**，只需：
- `AuthProvider`: no-op → **单用户访问口令 + 会话令牌**（公网必须有门）
- `LLMProvider`: 默认本机 Ollama → **默认云端 API（BYOK）**
- `ImageProvider`: 本机 ComfyUI 直连 → **待定（OPEN-009）**
- `AssetStore`: 本地卷 → 本地卷起步，可选对象存储
- 部署：单机 compose → **一台云服务器上的 compose + 反向代理 + 自动 HTTPS**

## Phase 1 PM 回传的关键约束（已并入 Spec 依据）

- **内容审核层必须设计为「可插拔 + 可关闭」**（补强 OPEN-001 的倾向）——要同时兼顾合规与创作自由，硬编码审核会劝退创作者
- **Tavern V2 卡须支持「多本世界书绑定 + 完整导出」**——这是打竞品「一张卡只带一本世界书、迁移即静默丢失」的核心差异点，属 P0 不能砍
- **P0 降级三项（PM 已裁定，纳入 MVP 范围）**：多后端管理面板 P0→P1；ComfyUI 由完整工作流编辑器降为「检测 + 出图 + 归档」轻量钩子；记忆由向量检索降为「关键词触发 + 自动摘要」
- **不降级项**：世界书触发 / 自动摘要 / 资产导入导出 / 内容审核
- **第一流失点 = 第 2 步「LLM 接入」**（酒馆正死于此）→ 首启向导 + 单后端接入的接口与错误分类已锁进契约（`error_class` 7 类）

## 变更记录

| 日期 | 变更内容 | 原因 |
|---|---|---|
| 2026-10-09 | 建档，录入 OPEN-001 ~ OPEN-004 | Phase 0 需求澄清发现 4 项待定 |
| 2026-10-09 | 录入 OPEN-005 ~ OPEN-007；关闭 001/002/004/006/007 | Phase 1 三文档调研 + 门禁三轮打回 |
| 2026-10-09 | 录入 OPEN-008（发行形态） | 用户提问是否做成游戏上 Steam |
| 2026-10-09 | 关闭 OPEN-003 / 005 / 008；录入 OPEN-009；新增「用户形态变更」章节 | 用户四项决定：仅限自用 / 云端部署 / 定名提线 / 现代日常向验证 |
