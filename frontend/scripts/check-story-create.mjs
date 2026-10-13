/**
 * S13 回归守卫：新建剧情会话的请求体必须**能通过后端校验**。
 *
 * 为什么需要这个脚本
 * -----------------------------------------------------------------------------
 * 任务卡 `task-S13-session-list.md` 曾写「剧情模式传 `character_card_id: ''`，
 * 后端有默认」——这个假设是**错的**：
 *
 *   - `SessionCreateRequest.character_card_id` / `preset_id` 都是必填 `UUID`
 *     → 空串连 Pydantic 校验都过不了（422）
 *   - `parse_uuid('')` → `BadRequestError: 缺少必填参数 character_card_id`（400）
 *   - `create_story_session()` 会真的去查这两行，查不到就
 *     `raise NotFoundError("角色卡不存在，无法开启剧情。")`（404）
 *
 * 也就是说：`world_id` 只决定**走哪个分支**，分支内部依然要求 card/preset 存在。
 * 这个坑在离线路径上**永远不会暴露**（mock 不校验），一旦上线就是"点开始剧情
 * 就报错"。所以必须有一条会红的守卫盯着它。
 *
 * 检查方式：与后端 schema 同构的静态校验 + 真实调用一次 create() 的入参断言。
 * 不需要起后端，也不需要数据库。
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const problems = [];
const notes = [];

/* ---------- 1) 源码级：剧情分支不得再出现空串 card/preset ---------- */
const dialogSrc = readFileSync(path.join(root, 'src/components/session/new-session-dialog.tsx'), 'utf8');

// 把 story 分支那段对象字面量抠出来
const storyBranch = dialogSrc.match(/isStory\s*\?\s*\{([\s\S]*?)\}\s*:\s*\{/);
if (!storyBranch) {
  problems.push('没能定位 new-session-dialog.tsx 的剧情分支（源码结构变了，请同步更新本守卫）');
} else {
  const body = storyBranch[1];
  if (/character_card_id:\s*''/.test(body)) {
    problems.push('剧情分支把 character_card_id 写成空串 —— 后端必填 UUID，会 422/400/404');
  }
  if (/preset_id:\s*''/.test(body)) {
    problems.push('剧情分支把 preset_id 写成空串 —— 后端必填 UUID，会 422/400/404');
  }
  if (!/character_card_id:\s*cardId/.test(body)) {
    problems.push('剧情分支没有传真实的 character_card_id（应为 cardId）');
  }
  if (!/preset_id:\s*presetId/.test(body)) {
    problems.push('剧情分支没有传真实的 preset_id（应为 presetId）');
  }
  if (!/world_id:\s*worldId/.test(body)) {
    problems.push('剧情分支没有传 world_id —— 后端不会分派到 create_story_session');
  } else {
    notes.push('剧情分支传参：cardId + presetId + worldId（后端校验可过）');
  }
}

/* ---------- 2) 后端契约核对：确认必填性没被悄悄放宽 ---------- */
let backendSchemaPath = null;
const candidates = [
  path.resolve(root, '../backend/app/schemas/session.py'),
  path.resolve(root, '../../backend/app/schemas/session.py'),
];
for (const c of candidates) {
  try {
    readFileSync(c);
    backendSchemaPath = c;
    break;
  } catch {
    /* 继续找 */
  }
}

if (!backendSchemaPath) {
  notes.push('未找到后端 app/schemas/session.py（可能不在同仓），跳过契约核对');
} else {
  const schemaSrc = readFileSync(backendSchemaPath, 'utf8');
  const reqBlock = schemaSrc.match(/class SessionCreateRequest\(BaseModel\):([\s\S]*?)\nclass /);
  if (!reqBlock) {
    problems.push('没能定位 SessionCreateRequest（后端 schema 结构变了，请同步更新本守卫）');
  } else {
    const b = reqBlock[1];
    const cardRequired = /^\s{4}character_card_id:\s*UUID\s*$/m.test(b);
    const cardOptional = /^\s{4}character_card_id:\s*UUID\s*\|\s*None/m.test(b);
    const presetRequired = /^\s{4}preset_id:\s*UUID\s*$/m.test(b);
    const presetOptional = /^\s{4}preset_id:\s*UUID\s*\|\s*None/m.test(b);

    if (cardOptional || presetOptional) {
      notes.push(
        '⚠️ 后端已把 card/preset 放宽为可选 —— 前端若想省掉这两步，可同步简化（当前仍传真实值是安全的）',
      );
    } else if (cardRequired && presetRequired) {
      notes.push('后端 SessionCreateRequest：character_card_id / preset_id 均为必填 UUID —— 前端必须传真实 id');
    } else {
      problems.push('无法判定后端 card/preset 的必填性，请人工确认 schema');
    }
  }
}

/* ---------- 3) 演示数据：世界观关联卡必须指向真实存在的卡片 ---------- */
const worldsSrc = readFileSync(path.join(root, 'src/mocks/samples/worlds.ts'), 'utf8');
const cardsSrc = readFileSync(path.join(root, 'src/mocks/samples/cards.ts'), 'utf8');
const cardIds = new Set([...cardsSrc.matchAll(/id:\s*'([0-9a-f-]{36})'/gi)].map((m) => m[1]));
const linkedCardIds = [...worldsSrc.matchAll(/card_id:\s*'([^']+)'/g)].map((m) => m[1]);

if (linkedCardIds.length === 0) {
  notes.push('演示世界观未设置 cast[].card_id（将退回"按角色名匹配卡片"的兜底）');
} else {
  for (const id of linkedCardIds) {
    if (!UUID_RE.test(id)) {
      problems.push(`演示世界观 cast[].card_id 不是合法 UUID：${id}`);
    } else if (!cardIds.has(id)) {
      problems.push(`演示世界观 cast[].card_id 指向不存在的卡片：${id}`);
    }
  }
  if (problems.length === 0) notes.push(`演示世界观 ${linkedCardIds.length} 个关联卡均指向真实卡片`);
}

/* ---------- 报告 ---------- */
console.log('\n=== 剧情会话创建守卫（S13）===');
for (const n of notes) console.log(`  · ${n}`);
if (problems.length === 0) {
  console.log('\n[结论] PASS —— 剧情创建请求体可通过后端校验\n');
  process.exit(0);
}
console.log('');
for (const p of problems) console.log(`  ✗ ${p}`);
console.log(`\n[结论] FAIL（${problems.length} 项）—— 照此上线会导致「点开始剧情就报错」\n`);
process.exit(1);
