# task-S16 · 对话配图（文生图接入）

> 状态：🟡 **后端触发已实现**（2026-10-14），剩「前端展示」
> 上游计划：[`09-project-plan.md`](./09-project-plan.md) §4.6
> 踩坑记录：[`04-pitfalls.md`](./04-pitfalls.md) §C2

---

## 1. 目标

在剧情对话中「不时插入图片」——不是每轮出图，而是**关键节点自动配一张**。

---

## 2. 已完成（2026-10-14）

### 2.1 出图链路端到端跑通

**验证脚本**：`scripts/verify-image-round1.sh`（可重复执行）

**实测结果**（全部 PASS）：

```
=== [1/5] 登录 ===                      HTTP 200  OK
=== [2/5] 提交出图任务（同步执行） ===   HTTP 202  (耗时 12s)
    status   = done
    archived = True
    asset_id = 300c9237-8fca-40ba-823e-c0469e1cb893
    error    = None
=== [4/5] 取回归档资产 ===              HTTP 200  291577 bytes
=== [5/5] 校验图片魔数 ===              ffd8ffe0... 合法 JPEG
```

**证据图**：`docs/asset/evidence-image-e2e-v2.jpg`（1024×1024）

**这证明的链路**：
```
前端请求 → ImageHook.submit（建 image_jobs 行）
        → CloudImageProvider.generate（调火山 /api/v3/images/generations）
        → ImageHook._finalize_done（落存储 + 建 kind=generated 资产 + 回填 asset_id）
        → GET /api/v1/assets/{id}/content 取回二进制
```

### 2.2 代码修复（2 处真实缺陷）

| 文件 | 改动 | 原因 |
|---|---|---|
| `backend/app/adapters/image.py` | 请求体加 `"watermark": False` | 火山默认给图加「AI 生成」角标 |
| `backend/app/adapters/image.py` | `content_type` 改为**按字节嗅探** | 火山回 JPEG，旧代码硬编码 `image/png` |

**回归守卫**：`backend/tests/test_image_adapter.py`（13 条）

其中 `test_jpeg_does_not_get_png_label` 是点名守卫：
把嗅探改回硬编码 `image/png`，该用例立刻 FAIL。

### 2.3 构建加速（已固化进 docker-compose）

`backend/Dockerfile` 的三个 `ARG` 已接到 `docker-compose.yml` 的 `build.args`，
本地只要在 `.env` 写三行就自动加速，**不再需要每次手敲 `--build-arg`**
（生产 `.env` 不写这三行 → 回落官方源，行为不变）：

```bash
# .env（本机，不入库）
NPM_REGISTRY=https://registry.npmmirror.com
PIP_INDEX_URL=https://mirror.sjtu.edu.cn/pypi/web/simple
PIP_TRUSTED_HOST=mirror.sjtu.edu.cn
```

**效果**：51 分钟 → 1 分 4 秒。

### 2.4 验证结论汇总

| 验证项 | 结果 |
|---|---|
| 后端全量单测（容器内 py3.12） | ✅ **458 passed**, 44 skipped |
| ruff 静态检查 | ✅ All checks passed |
| 出图端到端（含归档 + 取回） | ✅ 全 PASS |
| 协议兼容（尺寸/格式/路径） | ✅ `1024x1024` 直接可用，零改代码 |
| 账户充值后三模型可用性 | ✅ 5.0-pro / 4.0 / 5.0-flash 全部 HTTP 200 |

---

## 2.5 触发时机实现（2026-10-14 本轮核心）

**决策**（经用户确认）：触发策略 = **节点 + 新角色**；提示词 = **额外调一次 LLM 扩写**（模板兜底）；范围 = **后端触发 + 单测**。

### 新增 `backend/app/services/image_trigger.py`（约 520 行）

**两个纯函数 + 一个服务类**，全部不依赖 DB / 网络，可离线单测：

| 函数 | 职责 | 关键点 |
|---|---|---|
| `decide_image(...)` | 判定「这一轮要不要画」 | 返回 `TriggerDecision(should, reason, seed)` |
| `build_image_prompt(...)` | 无 LLM 时的模板拼装 | 从 `scene_patch` / 角色外观拼描述 |
| `next_story_state(...)` | 出图成功后回写记账 | 配额 / 轮次 / 节点去重 / 角色去重 |
| `ImageTriggerSvc` | 编排 `decide` + `render_prompt` | `render_prompt` 返回 `source` = `"llm"` / `"template"` |

### 判定顺序（**先节流后信号** —— 关键设计）

```
① 开关关闭      → SKIP_DISABLED
② 配额满        → SKIP_QUOTA      (默认 8 张/局)
③ 间隔不足      → SKIP_GAP        (默认 2 轮)
④ 节点触发且未画 → REASON_NODE     ← 最强信号（director.node_triggered）
⑤ 新角色未画过   → REASON_CAST     ← speakers 优先于 cast
⑥ 都不满足      → SKIP_NO_SIGNAL
```

> 顺序不能反：若先判信号再判节流，会在「节点触发但间隔不足」时留下歧义 reason，
> 前端无法区分「这轮本来就不该画」和「这轮想画但被节流了」。

### 提示词构造（LLM 扩写 + 模板兜底）

`_PROMPT_SYSTEM` 硬约束（防出「故事板」而非「画面」）：

- 只描述**画面**，不描述情节（描述「谁在做什么颜色的动作」，不写「于是主角决定…」）
- **绝不出现角色姓名** —— 必须改写成外观特征（否则模型画不出「鸣人」，只会画个路人）
- 只写**一个镜头**，不写分镜
- 不出现文字 / 招牌 / 字幕
- 60–120 汉字
- 输出 `{"prompt", "negative_prompt", "aspect"}` JSON

调用方式复用 `action_suggester.py` 的成熟模式：低 token（`max_tokens=400`）、
非流式、两级降级（先带 `response_format: json_object`，失败去掉重试）、
`_extract_prompt_json` 容错解析（裸 JSON + markdown 围栏 + 花括号切片兜底）、
**LLM 失败静默回落到模板，绝不让配图拖垮对话主流程**。

默认负面提示词：`文字, 水印, 签名, 乱码字符, 畸变, 多余手指, 低分辨率`

### 接入 `chat.py`

新增 `_story_image_events()`（约 90 行），两条路径：

1. **显式请求**（前端点「画一张」）→ 不受节流限制，走原有 `_maybe_image_events`
2. **自动触发** → `decide` → `render_prompt` → `aspect_to_size` → `generate_and_archive`
   → **成功后**才 `set_story(next_story_state(...))` 记账

> 记账必须在**成功之后**：否则出图失败也扣配额，等于「花了钱没拿到图还封了额度」。

SSE `image` 事件新增 `reason` 字段，前端可据此区分「节点图 / 角色图 / 手动图」。

### 新增配置（`config.py` + `story_state.py` + `docker-compose.yml`）

```python
# .env
STORY_IMAGE_ENABLED=true   # 默认 False，出图是花钱的功能，绝不默认开
STORY_IMAGE_QUOTA=8        # 8 × ¥0.30 ≈ ¥2.4 硬上限/局
STORY_IMAGE_MIN_GAP=2
```

`DEFAULT_STORY` 新增 4 个记账字段：`image_count` / `last_image_turn` /
`image_nodes` / `image_cast`。

### 测试

`backend/tests/test_image_trigger.py` —— **39 条**，6 个类：

| 类 | 条数 | 覆盖 |
|---|---|---|
| `TestTriggerRules` | 7 | 各 reason 分支 |
| `TestDedup` | 5 | 节点/角色去重 |
| `TestThrottle` | 7 | 配额、间隔 |
| `TestNextStoryState` | 4 | 状态回写 |
| `TestTemplatePrompt` | 4 | 模板兜底 |
| `TestAspectToSize` | 7 | 尺寸映射 |
| LLM 扩写 | 6 | `_FakeRouter` mock，含降级路径 |

其中 `test_dirty_gap_value_does_not_crash` 是**脏数据守卫**：`story` 里出现
`image_count: "bad"` 这类脏值时不得抛异常，由 `_as_int()` 宽容取整兜底。

---

## 3. 待办

### 3.1 账户侧 —— ✅ 已解决

用户已充值。复测三个 Seedream 模型全部 **HTTP 200**：

| 模型 | 充值前 | 充值后 |
|---|---|---|
| `doubao-seedream-5-0-pro-260628` | ❌ 403 `AccountOverdueError` | ✅ 可用（当前配置） |
| `doubao-seedream-4-0-20260415` | ✅ 可用 | ✅ 可用 |
| `doubao-seedream-5-0-flash-260915` | ❌ `ModelNotOpen` | ✅ 可用 |

> 仍有用的提醒：建议在[费用中心](https://console.volcengine.com/finance)
> 设**推理限额**，避免额度用尽后静默转付费。

### 3.2 触发时机 —— ✅ 已实现（见 §2.5）

### 3.3 前端展示（**未开始，本轮明确不做**）

需要设计：图片如何插入消息流？（独立气泡 / 旁白配图 / 时间线插图）

后端已就绪，前端拿到 SSE `image` 事件即可渲染，事件字段：
```jsonc
{ "type": "image", "asset_id": "...", "url": "...", "reason": "node", "prompt": "..." }
```

### 3.4 角色一致性参考图（**未开始**）

当前每张图独立生成，同一角色跨图长相会漂移。
后续可选：以首张角色图为 `reference_image` 传给 Seedream 做 img2img 锚定。

---

## 4. 复现命令

```bash
# 1. 起栈（加速源已固化进 compose，直接 build 即可）
cd /workspace/marionette-git
docker compose build api && docker compose up -d

# 2. 端到端验证（出图 → 归档 → 取回）
bash scripts/verify-image-round1.sh

# 3. 全量回归（必须在容器内跑，宿主机 py3.11 太旧，PEP 695 语法解析失败）
docker exec marionette-api sh -c "cd /app && ruff check app/ tests/ && python -m pytest tests/ -q"

# 4. 触发逻辑专项
docker exec marionette-api sh -c "cd /app && python -m pytest tests/test_image_trigger.py -q"

# 5. 确认容器内配置已注入
docker exec marionette-api python -c "
from app.core.config import get_settings
s = get_settings()
print(s.story_image_enabled, s.story_image_quota, s.story_image_min_gap)"
```

---

## 5. 关键提醒

> ⚠️ **别再用「某模型出图失败」推断「配置错了」。**
> 同一个 Key 下，模型 A 可能因额度耗尽 403，模型 B 照常出图。
> 排查顺序：**分模型实测 → 读错误码语义 → 最后才怀疑代码**。

> ⚠️ **`.env` 绝不入库。** 已被 `.gitignore` 覆盖（已实测 `git check-ignore` 确认）。
> 换密钥时改 `.env` 后 `docker compose up -d api` 热替换即可。

---

## 6. 变更记录

| 日期 | 内容 |
|---|---|
| 2026-10-14 | 出图链路端到端跑通；修复水印 + MIME 两处缺陷；新增 13 条回归守卫；构建加速 51min→1min |
| 2026-10-14 | 账户充值复测三模型全绿；**实现触发时机**（`image_trigger.py` 520 行 + 39 条单测）；接入 `chat.py`；补 compose 透传；加速源固化进 compose |
