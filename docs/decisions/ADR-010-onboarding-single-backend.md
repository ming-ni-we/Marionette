# ADR-010: 首启向导化 + 单 LLM 后端接入 + 统一错误分类（回应 OPEN-002 / PRD F1）

## Status
Accepted (2026-10-09)

## Background
PRD §9 判定**第 2 步「LLM 接入」是第一流失点**（酒馆正死于此）。PM 倾向"统一 OpenAI 兼容适配层，v1 默认接国内 API，本地模型作为可选后端"；但用户环境为 Windows + RTX 5060 Ti 16GB 且已部署 ComfyUI，本机推理具备现实条件。需裁决默认策略并锁定接口与错误分类枚举。

## Decision
1. **统一 OpenAI 兼容适配层**：单实现 `LLMProvider`，provider 枚举 `ollama | openai_compatible | zhipu | dashscope | deepseek`；云端与本地走同一协议，差异仅在 base_url/key/model。
2. **v1 仅单后端**（`GET/PUT /api/v1/config/llm`），多后端管理面板归 P1。
3. **默认策略 = 自动探测优先**：首启向导先探测本机 Ollama（`http://host.docker.internal:11434/v1`）；命中则默认本地；未命中则引导填云端 key。**不强迫用户做选择**，兼顾"数据私有/零成本"与 PM 的"接云更省心"。
4. **连通性自检 + 错误分类枚举（锁定）**：`POST /api/v1/config/llm/test` 3 秒内返回 `ok` 与 `error_class`：
   `model_not_found` / `endpoint_invalid`（端点缺 `/v1`） / `auth_failed` / `quota_exhausted`（余额为 0） / `network_unreachable` / `timeout` / `unknown`，每类配**中文修复指引**。
5. 配套 `GET /system/selfcheck`（Docker/DB/GPU/端口/ComfyUI 自检）与 `POST /onboarding/samples`（内置 3-5 张示例卡），支撑"15 分钟链路"。

## Consequences
- 正面：把"配一整套后端"压缩成"填一项 + 明确自检"；本地/云双路径都短；错误可归因、可自助修复。
- 负面：需维护 provider 差异（少量，OpenAI 兼容已收敛）；自检需跨容器探测宿主机（Windows 用 `host.docker.internal`）。
- 约束：API key 本地加密存储、读取脱敏；不采集隐私、不上报云端（符合 PRD §13）。

## Related ADRs
- ADR-003（后端）
- ADR-006（本地推理运行时）
- ADR-009（部署形态）
