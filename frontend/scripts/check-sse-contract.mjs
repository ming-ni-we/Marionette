/**
 * SSE 契约一致性检查（双白名单 + 后端对齐）
 * -----------------------------------------------------------------------------
 * 为什么需要它：本项目 SSE 事件名分散在**三处**，任何一处漏改，前端都会在
 * `dispatchFrame` 里静默丢弃事件（不报错、不告警），表现为「页面卡住」这类
 * 极难定位的问题。这个脚本把三处拉到一起比对，让漏改变成**编译前就能发现**的失败。
 *
 *   1. `src/api/types/session.ts`  → `SseEventMap` 的键（类型层白名单）
 *   2. `src/api/client/stream.ts`  → `KNOWN_EVENTS` 数组（运行时白名单）
 *   3. `backend/app/services/chat.py` → `EVT_*` 常量（真正的发出方）
 *
 * 注意第 3 项：后端 `EVT_*` 常量是**全量**事件名，1v1 与剧情模式共用；
 * 前两项必须覆盖它，不能少。反之多余（前端有、后端没有）也要报错。
 *
 * 用法：node scripts/check-sse-contract.mjs
 * 退出码非 0 表示契约不一致。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const repo = path.resolve(root, '..');

const read = (p) => fs.readFileSync(p, 'utf8');

/* ---------------------- 1) 类型层：SseEventMap 的键 ---------------------- */
const typesSrc = read(path.join(root, 'src/api/types/session.ts'));

function parseEventMapKeys(src) {
  // 抓 `export type SseEventMap = { ... };` 块，块内形如 `  name: Type;`
  const m = src.match(/export type SseEventMap\s*=\s*\{([\s\S]*?)\n\};/);
  if (!m) throw new Error('未找到 SseEventMap 定义');
  const keys = [];
  for (const line of m[1].split('\n')) {
    const hit = line.match(/^\s{2}([a-z_][a-z0-9_]*)\s*:/i);
    if (hit) keys.push(hit[1]);
  }
  return keys;
}

/* ------------------- 2) 运行时层：KNOWN_EVENTS 数组 ----------------------- */
function parseKnownEvents(src) {
  const m = src.match(/export const KNOWN_EVENTS[^=]*=\s*\[([\s\S]*?)\];/);
  if (!m) throw new Error('未找到 KNOWN_EVENTS 定义');
  return [...m[1].matchAll(/'([a-z_][a-z0-9_]*)'/gi)].map((x) => x[1]);
}

/* --------------------- 3) 后端：EVT_* = "name" 常量 ---------------------- */
function parseBackendEvents(src) {
  return [...src.matchAll(/^EVT_[A-Z_]+\s*=\s*"([a-z_][a-z0-9_]*)"/gim)].map((x) => x[1]);
}

const mapKeys = parseEventMapKeys(typesSrc);
const known = parseKnownEvents(read(path.join(root, 'src/api/client/stream.ts')));

const chatPath = path.join(repo, 'backend/app/services/chat.py');
let backend = [];
if (fs.existsSync(chatPath)) {
  backend = parseBackendEvents(read(chatPath));
} else {
  console.warn('[warn] 未找到后端 chat.py，跳过后端对齐检查');
}

/* ------------------------------ 比对 ----------------------------------- */
const uniq = (a) => [...new Set(a)];
const setOf = (a) => new Set(a);
const diff = (a, b) => a.filter((x) => !b.has(x));

const mapSet = setOf(mapKeys);
const knownSet = setOf(known);
const backendSet = setOf(backend);

const problems = [];

// 2 与 1 必须严格同构（顺序可比对，但这里只要求集合相等 —— 顺序不影响正确性）
const onlyInMap = diff(uniq(mapKeys), knownSet);
const onlyInKnown = diff(uniq(known), mapSet);
if (onlyInMap.length) {
  problems.push(`SseEventMap 有但 KNOWN_EVENTS 缺（事件会被静默丢弃）：${onlyInMap.join(', ')}`);
}
if (onlyInKnown.length) {
  problems.push(`KNOWN_EVENTS 有但 SseEventMap 缺（类型层不认，永远收不到）：${onlyInKnown.join(', ')}`);
}

// 后端发出的每个事件，前端都必须认识
if (backendSet.size) {
  const missingBackend = diff(uniq(backend), mapSet);
  if (missingBackend.length) {
    problems.push(`后端会发但前端白名单缺：${missingBackend.join(', ')}`);
  }
  const frontendOnly = diff(uniq(mapKeys), backendSet);
  if (frontendOnly.length) {
    problems.push(`前端白名单有但后端从不发（疑似笔误）：${frontendOnly.join(', ')}`);
  }
}

/* ------------------------------ 快照断言 -------------------------------- */
const STORY_EVENTS = ['director', 'speaker_switch', 'node', 'actions'];
const EXPECTED_1V1 = ['world_info', 'start', 'delta', 'usage', 'image', 'done', 'error'];
const EXPECTED_TOTAL = EXPECTED_1V1.length + STORY_EVENTS.length; // 11

if (mapKeys.length !== EXPECTED_TOTAL) {
  problems.push(`SseEventMap 事件数应为 ${EXPECTED_TOTAL} 个，实为 ${mapKeys.length} 个`);
}
for (const e of [...EXPECTED_1V1, ...STORY_EVENTS]) {
  if (!mapSet.has(e)) problems.push(`SseEventMap 缺事件：${e}`);
}
for (const e of STORY_EVENTS) {
  if (!knownSet.has(e)) problems.push(`KNOWN_EVENTS 缺剧情事件：${e}`);
}

/* ------------------------------ 报告 ----------------------------------- */
console.log('=== SSE 契约一致性检查 ===');
console.log(`SseEventMap (${mapKeys.length}):  ${mapKeys.join(', ')}`);
console.log(`KNOWN_EVENTS (${known.length}):  ${known.join(', ')}`);
if (backendSet.size) console.log(`后端 EVT_*  (${backend.length}):  ${uniq(backend).join(', ')}`);

if (problems.length === 0) {
  console.log(`\n[结论] PASS —— 双白名单同构，共 ${mapKeys.length} 个事件（含 ${STORY_EVENTS.length} 个剧情事件）`);
  process.exit(0);
}

console.error('\n[结论] FAIL');
for (const p of problems) console.error('  ✗ ' + p);
process.exit(1);
