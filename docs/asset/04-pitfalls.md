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

### D9. ⚠️ 同一契约有两个入口，只修了一个（S13 修复的世界编辑页「开演」必失败）

**现象**：世界编辑页点「用这个世界开演」弹 toast
「无法开演 —— 创建剧情会话失败。请确认后端已配置模型，并且这个世界至少有一个角色。」

toast 文案把人引向「配模型 / 加角色」，**但真实原因与模型和角色数都无关** ——
世界明明有 2 个角色、后端模型也配好了。

**根因**：创建剧情会话的**前端入口有两个**：

| 入口 | 文件 | S13 是否修了 |
|---|---|---|
| 会话列表页「新建」对话框 | `new-session-dialog.tsx` | ✅ 修了 |
| **世界编辑页「用这个世界开演」** | `world-editor.tsx` | ❌ **漏了** |

`world-editor.tsx` 的写法与被修掉的那份**一字不差**：

```ts
character_card_id: lead?.card_id ?? '',
preset_id: '',          // ← 后端必填 UUID
```

后端三道关卡都拦得住（实测）：

| 入参 | 结果 |
|---|---|
| `preset_id: ''` | `400 endpoint_invalid` |
| `character_card_id: ''` | `400 endpoint_invalid` |
| `preset_id: <不存在的 UUID>` | `404 model_not_found` |

**为什么闸门没拦住**：守卫 `check-story-create.mjs` **只扫 `new-session-dialog.tsx`
一个文件**。修完它之后闸门全绿，第二个入口从未进入扫描范围 ——
闸门给了一种**虚假的安全感**。

**修法**：
1. `world-editor.tsx` 复用对话框那套 `linkedCardId`（三级优先）+ `defaultPresetId`，
   自动补全真实 id；
2. 加 `canPlay` / `playBlockReason`，缺卡或缺预设时**按钮直接禁用 + title 说明原因**，
   而不是等提交后再弹一个**归因错误**的 toast；
3. 守卫改为**递归扫描 `src/` 下所有 `sessionsApi.create(` 调用点**，
   覆盖 `?? ''` 兜底变体。

**教训**（比坑本身更重要）：

> **修一个契约错误时，先枚举「所有具备该契约的调用点」，再逐个处理；
> 守卫脚本的扫描范围必须覆盖全仓，不能只盯症状出现的那个文件。**

顺带一个产品教训：**错误提示要指向真实原因**。这里的 toast 把用户往
「配模型 / 加角色」上带，排查成本被凭空放大 ——
提示文案写错，等价于制造一个新的 bug。

### D10. ⚠️ 修复已提交，但从未部署 —— 「代码对了，线上还是错的」

**现象**：D9 修完、提交 `2872bc5`、六项校验全绿之后，用户在线上点「开演」**依然失败**。

**根因**：线上前端跑的还是**旧版构建产物**。实测对照（都是压缩后的 JS）：

| 特征 | 线上 `index-DAZGvsr6.js` | 本地新构建 `index-DCcJtofX.js` |
|---|---|---|
| `playBlockReason` | 0 | **2** |
| `_turnKey` | 0 | **3** |
| `preset_id:""`（旧空串写法） | **1** | 0 |

`2872bc5` 从未进入线上镜像。

**为什么不能只替换文件**：前端产物被**烤进 api 镜像**
（`backend/Dockerfile` 的 `COPY --from=web /src/frontend/dist /app/static`），
所以更新前端 = **重新构建 api 镜像 + 重启容器**。

**已修复（2026-10-13）**：用户提供 SSH 凭据后完成部署。
线上产物 `index-DAZGvsr6.js` → **`index-CD95XgpK.js`**，特征齐全，
开演 201、两轮气泡落库顺序均验收通过。完整过程见
`07-status-and-backlog.md` §5.8 问题②、`task-INFRA-ops.md`「待办 X」。

⚠️ 部署时另一个坑：`docker-compose.yml` 用**相对路径**挂数据
（`./data/pgdata`、`./data/assets`、`./data/caddy`）。若在**新目录**直接
`docker compose up`，会**新建一套空数据库**、生产数据读不到。
正确做法是**只在新目录构建镜像，回原目录 `/opt/marionette` 替换重启**
（`--no-deps --force-recreate api`）。

**教训**：

> **「修好了」和「上线了」是两件事。**
> 提交、校验全绿只能证明**仓库里的代码对了**，不能证明**用户那边看到的东西变了**。
> 报告修复完成前，必须先在**用户实际访问的那个地址**上验证（或明确声明"未部署"）。
> 本项目的验收判据是：`curl <线上地址>/` 拿到的 `index-*.js` 文件名，
> 与本次构建产物名一致，且新包特征齐全。

### D11. ⚠️ 同一角色每轮 `speaker_id` 相同 → 第二轮回复写到第一轮气泡里

**现象**：剧情会话里连续游玩两轮。第二轮回答提交后，角色的回复与剧情推演
**没有出现在本轮用户气泡下方**，而是被追加到了**第一轮**的历史气泡里
（位置上在用户消息**上方**）—— 用户描述为「我说完话，角色的话跑到我上面去了」。

**根因**：`delta` 事件只带 `speaker_id`，不带任何轮次信息。前端靠它在
消息数组里**反向查找**该写进哪条气泡：

```ts
for (let i = next.length - 1; i >= 0; i -= 1) {
  if (next[i].meta?.speaker_id === speakerId) { /* 追加到这里 */ }
}
```

但**同一个角色每一轮的 `speaker_id` 完全相同**。第二轮该角色的 delta 会命中
第一轮留下的旧气泡（数组里更靠前、位于本轮用户消息之上）。
旁白分支（`speaker_id === null` 时找 `is_narration`）有同一缺陷。

**修法**：引入**轮次边界** `_turnKey`。

- `session.ts`：`MessageMeta` 新增 `_turnKey?: string`（纯前端本地，不参与请求）
- `use-chat-stream.ts`：
  - 新增 `turnKeyRef`，在 **`startStream`**（不是 `send`）里换新值 ——
    这样 `regenerate` / `retry` 也走同一条路径，不会漏
  - 新增 `tagTurn()`，给本轮产生的每条气泡打标记
  - `appendDelta` **两处**反查都加 `_turnKey === turnKeyRef.current` 条件
- 用户气泡**不需要**打标记（它不参与反查）

**为什么闸门一开始没拦住**：已有探针 `probeStoryRuntime` 只跑**一轮**，
一轮之内不存在「同角色历史气泡」，bug 根本不可见。
新增 `probeStoryMultiTurn`：连发两轮，断言 DOM 顺序为
「第二轮用户气泡 → 本轮回复气泡」，且**第一轮气泡没有被追加改写**。

**探针自己的两个坑**（写的时候踩的）：

| 坑 | 现象 | 修法 |
|---|---|---|
| 用户气泡没有 `p.narrative` | 那是**角色**正文的类名，取用户消息文本得到空串 | `readBody` 对用户气泡退化为取整块 `textContent`，再去掉前缀「你」 |
| `ok` 判定漏项 | 只判了「第二轮回复在用户之后」，没判「第一轮气泡没被改写」→ 故障注入后探针**仍 PASS**（漏报） | `ok = secondUserIdx >= 0 && secondReplyIdx > secondUserIdx && !firstTurnReplyGrew` |

> **教训**：**探针必须做故障注入验证**——把修复改回错误版本，探针要能 FAIL。
> 一个从不失败的探针等于没有探针。这次第二个坑正是靠这一步发现的。

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
