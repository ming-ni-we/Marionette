# task-S16 · 对话配图（文生图接入）

> 状态：🟡 **出图链路已跑通**（2026-10-14），剩「触发钩子 + 前端展示」
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

### 2.3 构建加速（本地调试用）

`backend/Dockerfile` 加了三个 `ARG`（**默认仍为官方源，不改变生产构建行为**）：

```bash
docker compose build api \
  --build-arg PIP_INDEX_URL=https://mirror.sjtu.edu.cn/pypi/web/simple \
  --build-arg PIP_TRUSTED_HOST=mirror.sjtu.edu.cn \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com
```

**效果**：51 分钟 → 1 分 4 秒。

### 2.4 验证结论汇总

| 验证项 | 结果 |
|---|---|
| 后端全量单测（容器内 py3.12） | ✅ **419 passed**, 44 skipped |
| ruff 静态检查 | ✅ All checks passed |
| 出图端到端（含归档 + 取回） | ✅ 全 PASS |
| 协议兼容（尺寸/格式/路径） | ✅ `1024x1024` 直接可用，零改代码 |

---

## 3. 待办

### 3.1 账户侧（阻塞项，需用户处理）

当前账号 `2132988262` 处于**欠费状态**（`AccountOverdueError`）：

- ✅ **`doubao-seedream-4-0-20260415`** —— 免费额度尚存，**可正常出图**（当前配置用它）
- ❌ `doubao-seedream-5-0-pro-260628` —— 额度耗尽，403
- ❌ `doubao-seedream-5-0-flash-260915` —— **未开通**，需控制台点「开通服务」

**要做的**：
1. 若要长期用 → 在[费用中心](https://console.volcengine.com/finance)充值
2. 若要试 flash → 在[开通管理](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement)开通
3. 建议设**推理限额**，避免免费额度用尽后自动转付费

### 3.2 触发时机设计（核心开发工作）

见 [`09-project-plan.md`](./09-project-plan.md) §4.6.3。要点：

| 触发时机 | 数据来源 | 优先级 |
|---|---|---|
| 节点触发（`node_triggered`） | 导演 `node` 事件已有 | 🔴 最高 |
| 新角色登场 | cast 变化 | 🔴 高 |
| 场景切换 | `scene.location` 变化 | 🟡 中 |
| 玩家手动点「画一张」 | 前端按钮 | 🟡 中 |

**成本估算**：每 5 轮配 1 张 → 20 轮一局 = 4 张 ≈ **¥0.9/局**。

### 3.3 前端展示

需要设计：图片如何插入消息流？（独立气泡 / 旁白配图 / 时间线插图）

---

## 4. 复现命令

```bash
# 1. 起栈
cd /workspace/marionette-git
docker compose build api \
  --build-arg PIP_INDEX_URL=https://mirror.sjtu.edu.cn/pypi/web/simple \
  --build-arg PIP_TRUSTED_HOST=mirror.sjtu.edu.cn \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com
docker compose up -d

# 2. 端到端验证（出图 → 归档 → 取回）
bash scripts/verify-image-round1.sh

# 3. 全量回归（必须在容器内跑，宿主机 py3.11 太旧）
docker exec marionette-api sh -c "cd /app && python -m pytest tests/ -q"

# 4. 单测回归（图像适配器专项）
docker exec marionette-api sh -c "cd /app && python -m pytest tests/test_image_adapter.py -q"
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
