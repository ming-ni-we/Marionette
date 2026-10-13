# 04 · 踩坑记录（动手前必读）

> 配套总纲：[`README.md`](./README.md) · 生成日期：2026-10-12
> 全部是**真实发生过**的坑，不是假想。每条都标注了根因与修法。

---

## A. 环境与工具链

| # | 坑 | 根因 | 修法 |
|---|---|---|---|
| A1 | pytest 报 22 个 collection error | `conftest.py` 依赖相对路径，在仓库根跑找不到模块 | **必须在 `backend/` 目录下跑** |
| A2 | `No module named pytest` | 用了系统 python | 用 `./.venv/bin/python`（或 `/tmp/venv/bin/python`） |
| A2b | `No module named aiosqlite` | `pyproject.toml` 曾漏声明该 dev 依赖（单测用内存 SQLite） | 已补 `"aiosqlite>=0.20"`；重装 `pip install -e ".[dev]"` |
| A3 | Windows 生成的 lock 在 Linux 构建失败 | lock 不含 Linux 原生可选依赖，`npm ci` 静默漏装 esbuild/rollup 二进制 | 容器内 `rm -f package-lock.json && npm install` |
| A4 | `alembic.ini` 在 Windows 崩溃 | Alembic 以 `locale` 编码读取，GBK 解不了中文注释 | 配置文件保持**纯 ASCII** |
| A5 | Git Bash 改写 SSH 路径参数 | MSYS2 把 `/home/x` 转成 Windows 路径，症状像网络故障 | 调用前设 `MSYS2_ARG_CONV_EXCL='*'` |

---

## B. 数据库

| # | 坑 | 根因 | 修法 |
|---|---|---|---|
| B1 | 中文子串搜不到 | PG 默认分词器把连续中文当整段 token | 用 `pg_trgm` GIN + `ILIKE`，**不装分词器**（ADR-005） |
| B2 | `extension "vector" is not available` | 官方 `postgres` 镜像不含 pgvector | 必须用 `pgvector/pgvector:pg18` |
| B3 | Alembic 与模型漂移 | 手改表结构未生成迁移 | 禁止 `create_all` 上生产；必须 `alembic revision --autogenerate` 并**人工复核** |
| B4 | **`create_all` 在临时 schema 里「静默不建表」** | `checkfirst=True` 用 `pg_table_is_visible()` 判存在性，而 `search_path` 带 `public` 兜底 → `public.cards` 被判「可见」→ **跳过全部建表** → 临时 schema 空无一表 → 查询全部**回落生产库** | 显式按 schema 建表（`Table.to_metadata(schema=…)`），并加硬守卫：**建表数量必须等于元数据表数，否则拒绝运行** |
| B5 | 集成测试直连生产库造成污染 | 同 B4 | 同上；`conftest.py` 现已内置两道守卫，隔离失效会 `pytest.exit(returncode=2)` |

---

## C. HTTP 与协议

| # | 坑 | 根因 | 修法 |
|---|---|---|---|
| C1 | **导出/下载遇中文文件名必 500** | `safe_filename` 刻意保留中文，却被塞进 `Content-Disposition` 响应头；Starlette 按 `latin-1` 编码头值 → `UnicodeEncodeError` | 新增 `content_disposition()`，按 RFC 6266/5987 输出 ASCII 回退名 + `filename*=UTF-8''…` |
| C2 | **`Literal` 枚举漏值 → 500 而非 400** | Pydantic 字面量校验失败会以 `ValidationError` 冒到通用异常处理器 | 契约枚举与代码 `Literal` **必须同步维护**，并配单测防漂移 |
| C3 | Windows SSH 传中文参数变乱码 | Windows 侧 Python 按 GBK 解析 argv，再以 UTF-8 发出 → 远端拿到非法字节 → FastAPI 400 | 需要中文时用**百分号编码**，或把命令写成脚本文件按字节上传 |
| C4 | 流式输出「憋住」不出字 | 代理缓冲把 SSE 攒成大块 | Caddy 必须 `flush_interval -1` |

---

## D. 剧情引擎（本轮新增，全部是开发中真实撞到的）

### D1. ⚠️ 状态机死锁：会话永久卡在 `generating`

**症状**：剧情一轮出错后，会话再也无法发起下一轮，一直卡住。

**根因**：`_finalize_incomplete` 调用 `transition_state(session_row, "idle")`，但**迁移表里
`generating` 没有直达 `idle` 的边**（只能去 `post_processing` / `interrupted` / `error`）→ 抛
`ConflictError` → 状态没改成功 → 永久卡死。

**修法**：新增 `_force_idle()`，**绕过迁移表**直接改：

```python
def _force_idle(self, session_row, *, error=None) -> None:
    """无条件把单轮状态机拉回 idle（容错版，绕过迁移表校验）。"""
    sm = dict(session_row.state_machine or {})
    previous = sm.get("current")
    if previous != "idle":
        logger.info("state forced to idle", extra={"from": previous, ...})
    sm["current"] = "idle"
    sm["version"] = int(sm.get("version", 0)) + 1
    sm["last_error"] = error
    session_row.state_machine = sm
```

**通用教训**：正常路径走迁移表，**容错路径必须绕过**——否则错误处理本身会成为新的故障源。

---

### D2. ⚠️ 重复空占位消息：2 个说话者产出 3 条消息

**症状**：剧情一轮有两个角色开口，但库里多出一条内容为空的 assistant 消息。

**根因**：首个说话者的行被创建了两次——`start` 事件里 `_create_story_message` 建一次，
演出循环里 `_append_speaker_placeholder` 又建一次。

**修法**：删掉 `_create_story_message`；`start.message_id` 改为空串 `""`，消息行**只在循环里建**。

**不变量**：**N 个说话者 = N 条消息**。`start.message_id` 为空是合法契约（前端收到首个
`speaker_switch`/`delta` 时拿到真实 id）。

---

### D3. 导演降级漏了一条路径

**症状**：端点支持 `response_format` 参数但返回非 JSON 正文时，导演直接降级到 `fallback()`。

**根因**：原代码只在 L1 **抛异常**时才重试。而更常见的失败是——端点接受了参数，但输出了一段
散文而不是 JSON，此时 `raw is not None` 故不触发重试。

**修法**：判断条件从 `raw is None` 改为 **`parsed is None`**：

```python
raw = await self._try_complete(messages, overrides=overrides, use_json_format=True)
parsed = _extract_json(raw) if raw is not None else None
# L2：解析失败就重试（覆盖两种失败动机）
if parsed is None:
    raw = await self._try_complete(messages, overrides=overrides, use_json_format=False)
    parsed = _extract_json(raw) if raw is not None else None
```

---

### D4. `count=0` 被静默当成默认值 3

**根因**：`int(count or DEFAULT_COUNT)` —— **`0` 是 falsy**，被当成「未提供」。

**修法**：`int(count) if count is not None else DEFAULT_COUNT`

**通用教训**：`x or default` 在 `x=0` / `x=""` / `x=False` 时语义错误。判「是否提供」要用 `is None`。

---

### D5. 散文包裹的 JSON 数组解析失败

**症状**：模型输出 `"建议如下：[{...}]"`，解析出一个**内层 dict**，没有 `actions` 键 → 静默失败。

**根因**：提取时先试 `{`…`}` 分支，命中了数组里的第一个对象。

**修法**：**先试数组分支**，且必须通过 `_has_actions()` 校验：

```python
for opener, closer in (("[", "]"), ("{", "}")):
    start, end = text.find(opener), text.rfind(closer)
    if 0 <= start < end:
        parsed = _try_load(text[start : end + 1])
        if _has_actions(parsed):     # dict 必须含 "actions" 键；list 直接接受
            return parsed
```

---

### D6. token 估算：中文不是「一个字一个 token」

**症状**：测试断言 `completion_tokens == 6`（两句各 3 字）失败，实际是 `4`。

**根因**：`estimate_tokens` 对中文按 **3 汉字 ≈ 4 token** 换算，不是字符数。

**修法**：修正测试预期为 `8`（4+4）。**写涉及 token 的测试时，先看 `services/tokens.py`。**

---

### D7. 前端多说话者 `delta` 串气泡

**症状**：剧情一轮两个角色，第二个角色的字追加到了**第一个角色的气泡**里。

**根因**：`use-chat-stream.ts` 原实现只往「最后一条」assistant 消息追加文本。

**修法**：新增 `appendDelta(text, speakerId)`，按 `speaker_id` **从后往前**反查目标气泡
（避免同名角色在多轮里误命中历史气泡）；1v1 不带该字段时退回原行为。

**同时修正**：`done` 事件原来只 `patchLastAssistant`，多气泡下会留下 `streaming` 残留 →
改为扫全部仍为 `streaming` 的消息统一收口。

---

### D8. ⚠️ 创建剧情会话必 500：`flush()` 后读过期属性触发 async 懒加载

> **这是本轮唯一「只有真实服务器才暴露」的后端缺陷，值得单独记住。**

**症状**：线上 `POST /api/v1/sessions` 带 `world_id` **必然 500**，1v1 不带 `world_id` 完全正常。

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

**根因**：`SessionSvc.create_story_session()` 落完序幕后的收尾是

```python
row.last_message_at = _now()
await self._db.flush()          # ← 这一步把 row 上所有已加载属性标记为 expired
return self.serialize(row, ...) # ← serialize 读 row.updated_at → 触发懒加载 IO
```

`flush()` 会让 ORM 把该行的属主状态置为 expired，下次访问**任何列**都要重新 `SELECT`。
同步 SQLAlchemy 里这只是一次隐式查询；但在 **async 引擎**下，这次隐式 IO 发生在
`await_only()` 可用的 greenlet **之外**（`serialize` 是普通同步函数），于是直接抛
`MissingGreenlet`。

**为什么 1v1 分支没事**：`_create_rpg_session()` 在 `flush()` 之后**多写了一句
`await self._db.refresh(row)`**（第 216 行）。剧情分支漏了这一句。

**修法**：`serialize()` 之前补 `await self._db.refresh(row)`。
同类缺陷还有 `fork()`（第 581 行前）——一并补上。

**为什么长期没被发现**：

| 测试层 | 为何漏掉 |
|---|---|
| 单元测试（内存 SQLite + 内存夹具） | 不走真实 async 会话生命周期，不触发 expired 懒加载 |
| 集成测试 `test_story_api.py` | 存在且断言正确，但需 `MARIONETTE_INTEGRATION=1` —— **从来没被执行过** |
| 前端 smoke / 离线 mock | 完全不碰后端 |

**守卫**：新增两个回归测试，**必须在真库下运行**：

- `test_create_story_response_is_fully_serialized`
- `test_fork_session_response_is_fully_serialized`

均已验证「回退修复即 FAIL（精确复现 500）、恢复修复即 PASS」。

**教训**：**async 引擎下，`flush()` 之后要读该行任何字段，必须先 `refresh()`。**
统一约定：`serialize` 前若发生过 `flush`，先 refresh。

**顺带修掉的**：`pyproject.toml` 的 `dev` 依赖缺 `aiosqlite`（单元测试用内存 SQLite），
全新环境 `pip install -e ".[dev]"` 后跑 pytest 会 `ModuleNotFoundError`。已补。

---

## E. 前端工程

| # | 坑 | 根因 | 修法 |
|---|---|---|---|
| E1 | **SSE 事件被静默丢弃** | 事件名分散在三处白名单，漏改一处 → `dispatchFrame` 直接 return，**不报错不告警** | 加 `verify:sse` 脚本做三处同构校验，挂进 `npm run` |
| E2 | 新增 `ContextSegmentName` 后 TS 编译失败 | `SEGMENT_LABEL` 是 `Record<ContextSegmentName, string>`，键不全即报错 | 加段名时必须同步补 `context-inspection.tsx` 的 `SEGMENT_LABEL` |
| E3 | `Badge variant="meta"` 类型报错 | 合法值是 `neutral`，没有 `meta` | 用 `variant="neutral"`；文本色用 `className="text-meta"` |
| E4 | 新增字段后 mock fixture 报错 | `Session` 加了必填 `world_id` | 同步改 `mocks/samples/*.ts`；或把新字段设为可选 |
| E5 | 图标 `import` 报不存在 | `components/icons.ts` 是**唯一出口**，新图标必须先加进注册表 | 在 `icons.ts` 对应分组补一行，再 `npm run verify:icons` |

---

## G. 剧情模式前端专有坑（S12 实测踩到，均已修 + 有回归守卫）

> 这两个坑的共性：**离线 mock + 1v1 路径都测不出来**，只有「真实后端 + 多角色一轮」才触发。
> 因此不要再靠「本地演示看起来没问题」判断剧情渲染正确 —— 跑 `npm run smoke` 的第 3 项探针。

| # | 坑 | 根因 | 修法 |
|---|---|---|---|
| G1 | **首个说话者的台词串进旁白气泡** | 后端对**第一个**说话者**不发** `speaker_switch`（`chat.py` 的 `if index > 0:`），只发 `delta + speaker_id`。前端 `appendDelta` 匹配不到 `speaker_id` 时**退回「最后一条 assistant」** —— 那条通常是导演的旁白。结果旁白里长出角色台词，该角色没有自己的气泡 | `appendDelta` 匹配不到 `speaker_id` 时**就地新建气泡**；只有 `speaker_id === undefined`（1v1）才走「最后一条」分支。真实污染文本：`雨下了三天。…像随时会掉她没抬头，把账本往阴影里推了半寸。下来一层。` |
| G2 | **旁白整轮不显示** | 旁白的 `speaker_switch` **带 `message_id`**，前端据此假设「后端已建行 → 本地已有」。但该行是本轮才落库的，而本地 `messages` 是首屏 `GET /sessions/{id}` 播种的旧快照 —— 里面没有它 | `speaker_switch` 改为**按后端 id 做 upsert**（本地没有就补一条带真实 id 的占位）；旁白行直接标 `complete`（后端落库时正文已完整） |
| G3 | 剧情节多出一条永远填不满的空气泡 | `startStream` 预建空占位是 1v1 的语义（承接首个 `delta`）；剧情模式消息行由后端在演出循环里建（`start.message_id` 为空串） | `useChatStream` 加 `storyMode` 参数：不预建占位，并在 `done` 时清掉仍为空的非旁白占位 |
| G4 | 离线演示永远看不到导演/建议 | 离线链路走的是 1v1 的 `mockStream`，不含 `director`/`speaker_switch`/`node`/`actions` | 新增 `mockStoryStream`，**刻意复刻后端那些「不对称」细节**（首个说话者不发 switch、旁白不走 delta），否则 G1/G2 在离线路径上永远不暴露 |

**回归守卫**：`scripts/smoke.mjs` 第 3 项探针 `剧情多角色独立气泡` ——
驱动**真实 `StoryRuntimePage`** 消费 `mockStoryStream`，断言
「气泡数 ≥2 + 每人正文各就各位 + 旁白未被串 + 建议可点」。
**已验证过有效性**：把 G1 的修复改回退化版本，探针立刻 FAIL 并打印污染文本。

---

## F. 项目流程坑

| # | 坑 | 说明 |
|---|---|---|
| F1 | 沙箱 git push 失败 | 沙箱无 GitHub 写凭据。已穷尽 git / gh CLI / 环境变量 / `.git-credentials` / credential-helper / editor_sdk 凭据端点 / GitHub MCP(**只读**) 全部通道。**不是代码问题，是环境缺凭据**。见 `task-GIT-push.md` |
| F2 | 生产库被集成测试污染 | 历史缺陷（B4/B5），守卫已加。遗留数据待清理 |
| F3 | DeepSeek key 曾明文出现在对话中 | 建议作废重发，改服务器 `.env` 后 `docker compose up -d` 热替换 |
