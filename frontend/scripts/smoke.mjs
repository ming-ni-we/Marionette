/**
 * 运行时冒烟测试：在 jsdom 中真实挂载 App，逐路由渲染，
 * 断言「非空白 + 出现引导内容 + 无未捕获异常/console.error」。
 *
 * 注意：这是**开发期验证脚本**，不是产品代码；不参与 vite 构建。
 * 后端不可达（fetch 全部 reject）→ 触发各页面的离线演示兜底，正好验证 AC-16。
 */
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');

/* ---------------- 1) 用 esbuild 把 App 打成 node 可加载的 ESM ------------- */
const outfile = path.join(root, '.smoke-bundle.mjs');
await build({
  entryPoints: [path.join(here, 'smoke-entry.tsx')],
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node20',
  outfile,
  jsx: 'automatic',
  define: { 'process.env.NODE_ENV': '"production"' },
  alias: { '@': path.join(root, 'src') },
  loader: { '.css': 'empty' },
  logLevel: 'error',
  external: [],
});

/* ---------------------------------- 2) jsdom ------------------------------ */
const dom = new JSDOM('<!doctype html><html lang="zh-CN"><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
});

const { window } = dom;

// 补齐 jsdom 缺失、但 Radix / 我方代码会用到的浏览器 API
window.matchMedia =
  window.matchMedia ||
  ((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {
      return false;
    },
  }));
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
class IO {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
window.ResizeObserver = window.ResizeObserver || RO;
window.IntersectionObserver = window.IntersectionObserver || IO;
window.Element.prototype.scrollIntoView = function () {};
window.HTMLElement.prototype.scrollIntoView = function () {};
window.URL.createObjectURL = window.URL.createObjectURL || (() => 'blob:mock');
window.URL.revokeObjectURL = window.URL.revokeObjectURL || (() => {});
if (!window.PointerEvent) window.PointerEvent = window.MouseEvent;

// 后端不可达：所有 fetch 一律 reject（逼出离线演示兜底路径）
const fetchCalls = [];
window.fetch = (url) => {
  fetchCalls.push(String(url));
  return Promise.reject(new TypeError('smoke-test: offline (fetch stubbed)'));
};

// 把 jsdom 的全局挂到 Node 上，供打包后的代码使用
const g = globalThis;
for (const key of [
  'window',
  'document',
  'navigator',
  'location',
  'history',
  'localStorage',
  'sessionStorage',
  'matchMedia',
  'ResizeObserver',
  'IntersectionObserver',
  'PointerEvent',
  'HTMLElement',
  'Element',
  'Node',
  'Event',
  'CustomEvent',
  'MutationObserver',
  'getComputedStyle',
  'requestAnimationFrame',
  'cancelAnimationFrame',
  'fetch',
  'URL',
  'Blob',
  'FormData',
]) {
  try {
    Object.defineProperty(g, key, {
      value: window[key],
      configurable: true,
      writable: true,
    });
  } catch {
    // Node 内建只读全局（如 navigator）——跳过即可，jsdom 里已有可用实现
  }
}

// jsdom 里所有 HTML*/SVG* 元素构造器都要传给全局，否则 Radix 在 effect 里
// 引用 `instanceof HTMLFormElement` 等会 ReferenceError（真实浏览器中本就存在）。
const BLOCK = new Set([
  'Promise', 'Proxy', 'Reflect', 'Symbol', 'Array', 'Object', 'Function',
  'String', 'Number', 'Boolean', 'Date', 'RegExp', 'Error', 'Map', 'Set',
  'WeakMap', 'WeakSet', 'JSON', 'Math', 'Intl', 'BigInt', 'ArrayBuffer',
  'DataView', 'Uint8Array', 'Int8Array', 'Uint16Array', 'Int16Array',
  'Uint32Array', 'Int32Array', 'Float32Array', 'Float64Array', 'BigInt64Array',
  'BigUint64Array', 'globalThis', 'process', 'console', 'setTimeout',
  'clearTimeout', 'setInterval', 'clearInterval', 'setImmediate',
  'clearImmediate', 'queueMicrotask', 'structuredClone', 'fetch', 'Buffer',
]);
for (const key of Object.getOwnPropertyNames(window)) {
  if (BLOCK.has(key) || !/^[A-Z]/.test(key)) continue;
  if (key in g && !/Element$|^Text$|^Range$|^File$|^FileList$|^DataTransfer$|^XMLHttpRequest$|^AbortController$|^AbortSignal$|^DOMException$|^MessageChannel$|^MessagePort$|^NodeFilter$|^TreeWalker$|^DOMParser$|^XMLSerializer$/.test(key)) {
    continue;
  }
  const value = (() => {
    try {
      return window[key];
    } catch {
      return undefined;
    }
  })();
  if (value === undefined) continue;
  try {
    Object.defineProperty(g, key, { value, configurable: true, writable: true });
  } catch {
    /* ignore */
  }
}
g.IS_REACT_ACT_ENVIRONMENT = false;

/* ------------------------- 3) 逐路由挂载并断言 ---------------------------- */
const ROUTES = [
  { path: '/login', expect: /口令|登录|密码/ },
  { path: '/setup', expect: /自检|向导|模型|后端/ },
  { path: '/', expect: /内容库|角色卡|世界书|演示数据|新建/ },
  { path: '/cards/new', expect: /角色卡|新建|人设|预览/ },
  { path: '/worldbooks/new', expect: /世界书|条目|命中/ },
  { path: '/presets/new', expect: /预设|采样|温度|参数/ },
  { path: '/worlds', expect: /剧情世界|世界|新建世界/ },
  { path: '/worlds/new', expect: /基本信息|世界名称|角色群/ },
  { path: '/sessions', expect: /会话|新建会话|演示数据|剧情/ },
  { path: '/assets', expect: /素材|图集|出图|归档/ },
  { path: '/settings', expect: /设置|审核|模型后端|诊断/ },
  { path: '/this/route/does/not/exist', expect: /没有对应的页面|内容库/ },
  // 演示实体详情页（离线兜底后仍要渲染真实内容，验证 AC-16 + 差异化视觉点）
  {
    path: '/worldbooks/wb1f0a1e-0001-4b01-9a01-000000000001',
    expect: /命中测试/, // 右侧三态命中测试面板必须真实渲染
  },
  {
    path: '/sessions/s1f0a1e2-0001-4d01-9c01-000000000001',
    expect: /怀表/, // 只有演示消息正文里出现，证明历史被真正回填
  },
  { path: '/stories/s1f0a1e2-0001-4d01-9c01-000000000001', expect: /导演|旁白|行动/ },
  { path: '/cards/c1f0a1e2-0001-4a01-9f01-000000000001', expect: /苏晚/ },
  { path: '/presets/p1f0a1e2-0001-4c01-9b01-000000000001', expect: /日常向/ },
];

const { mount, mockStream, mockWorldBookTest, SAMPLE_WORLDBOOKS, probeStoryRuntime, probeSessionList } = await import(
  pathToFileURL(outfile).href
);

const errors = [];
const consoleErrors = [];
const origErr = console.error;
console.error = (...args) => {
  const line = args.map((a) => (a && a.stack ? a.stack : String(a))).join(' ').split('\n')[0];
  // React 的 act 提示等在 jsdom 下无意义，过滤掉噪声，但保留真实错误
  if (!/not wrapped in act|ReactDOMTestUtils/.test(line)) consoleErrors.push(line);
  origErr(...args);
};
const onUncaught = (e) => errors.push(String(e.reason || e.message || e));
window.addEventListener('unhandledrejection', onUncaught);
window.addEventListener('error', onUncaught);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const results = [];
for (const route of ROUTES) {
  const before = consoleErrors.length;
  let thrown = null;
  let rootRef = null;
  try {
    document.getElementById('root').innerHTML = '';
    rootRef = mount(route.path);
    await sleep(120); // 让初始 render + 失败的 query 走完第一轮
    await sleep(120);
  } catch (e) {
    thrown = String(e && e.stack ? e.stack : e);
  }
  const text = (document.body.textContent || '').replace(/\s+/g, ' ').trim();
  const newErrors = consoleErrors.slice(before);
  const ok =
    !thrown && text.length >= 40 && route.expect.test(text) && newErrors.length === 0;
  results.push({
    path: route.path,
    chars: text.length,
    matched: route.expect.test(text),
    thrown,
    consoleErrors: newErrors,
    ok,
  });
}

/* ---------------- 3.5) 差异化视觉点：三态命中判定 + SSE 事件链路 -------------- */

function probeHitTest() {
  const base = SAMPLE_WORLDBOOKS[0].data;
  const text = '雨天的怀表 与 豆浆摊 的 拆迁 公告，旧城区';
  // 把预算压到 300，逼出「命中但被挤出」这一态
  const res = mockWorldBookTest({ ...base, token_budget: 300 }, text, base.scan_depth);
  const miss = res.entries.filter((e) => !e.matched).length;
  const inBudget = res.entries.filter((e) => e.matched && e.in_budget).length;
  const evicted = res.entries.filter((e) => e.matched && !e.in_budget).length;
  return {
    ok: miss > 0 && inBudget > 0 && evicted > 0 && res.total_tokens <= 300,
    miss,
    inBudget,
    evicted,
    total: res.total_tokens,
    budget: res.token_budget,
  };
}

async function probeSse() {
  const seen = [];
  let closed = false;
  mockStream(
    (event, data) => seen.push({ event, data }),
    () => {
      closed = true;
    },
  );
  await sleep(3600);
  const names = seen.map((s) => s.event);
  const deltas = names.filter((n) => n === 'delta').length;
  const idx = (n) => names.indexOf(n);
  const last = names[names.length - 1];
  return {
    ok:
      closed &&
      deltas >= 3 &&
      names[0] === 'world_info' &&
      idx('start') > idx('world_info') &&
      idx('delta') > idx('start') &&
      idx('usage') > idx('delta') &&
      idx('done') > idx('usage') &&
      last === 'done',
    sequence: names.join(' → '),
    deltas,
    closed,
  };
}

const hit = probeHitTest();
const sse = await probeSse();
const story = await probeStoryRuntime();

/* ------------- 3.6) 会话列表的剧情集成（S13）------------- */
// 必须先清空 root：上一个探针（probeStoryRuntime）已把页面挂在同容器上。
document.getElementById('root').innerHTML = '';
const sl = await probeSessionList();

/* --------------------------------- 4) 报告 -------------------------------- */
console.error = origErr;
let failed = 0;
console.log('\n=== 运行时冒烟测试（jsdom 真实挂载）===');
console.log(`fetch 被拦截次数（应为 ≥1，证明走了离线兜底）：${fetchCalls.length}`);
for (const r of results) {
  const flag = r.ok ? 'PASS' : 'FAIL';
  if (!r.ok) failed += 1;
  console.log(
    `${flag}  ${r.path.padEnd(34)} 渲染 ${String(r.chars).padStart(4)} 字符  命中引导关键词=${r.matched}`,
  );
  if (r.thrown) console.log(`       抛错: ${r.thrown.split('\n')[0]}`);
  for (const e of r.consoleErrors) console.log(`       console.error: ${e}`);
}
console.log(`\n未捕获异常总数：${errors.length}`);
for (const e of errors.slice(0, 10)) console.log('  ', e.split('\n')[0]);

console.log('\n=== 差异化视觉点探针 ===');
console.log(
  `${hit.ok ? 'PASS' : 'FAIL'}  三态命中判定  未命中=${hit.miss} 命中且在预算内=${hit.inBudget} 命中但被挤出=${hit.evicted} (used ${hit.total}/${hit.budget})`,
);
console.log(`${sse.ok ? 'PASS' : 'FAIL'}  SSE 事件链路  ${sse.sequence}  delta=${sse.deltas}`);
console.log(
  `${story.ok ? 'PASS' : 'FAIL'}  剧情多角色独立气泡  气泡=${story.bubbles.length} 名字=[${story.bubbles
    .map((b) => b.name)
    .join('、')}] 行动建议=${story.suggestionCount} 旁白未被串=${story.narrationClean}`,
);
if (!story.ok) {
  for (const b of story.bubbles) {
    console.log(`       ${b.name || '(无名)'}: ${b.text.replace(/\s+/g, ' ').slice(0, 60)}`);
  }
  console.log(`       旁白: ${story.narrationText.replace(/\s+/g, ' ').slice(0, 60)}`);
}

const slOk =
  sl.hasStory &&
  sl.hasRpg &&
  sl.storyBadgeCount >= 1 &&
  sl.storyTitleShowsWorld &&
  sl.storyHrefOk &&
  sl.rpgHrefOk;
console.log(
  `${slOk ? 'PASS' : 'FAIL'}  会话列表剧情集成  条目=${sl.rows.length} 剧情标识=${sl.storyBadgeCount} 世界观名=${sl.storyTitleShowsWorld} 跳转=${sl.storyHrefOk ? '/stories' : '✗'}/${sl.rpgHrefOk ? '/sessions' : '✗'}`,
);
if (!slOk) {
  for (const r of sl.rows) {
    console.log(`       [${r.isStory ? '剧情' : '单人'}] ${r.title.slice(0, 60)}`);
  }
  if (!sl.hasStory) console.log('       ✗ 列表里没有剧情会话');
  if (!sl.hasRpg) console.log('       ✗ 列表里没有 1v1 会话');
}

const probeFailed =
  (hit.ok ? 0 : 1) + (sse.ok ? 0 : 1) + (story.ok ? 0 : 1) + (slOk ? 0 : 1);
console.log(
  failed === 0 && errors.length === 0 && probeFailed === 0
    ? '\n[结论] PASS'
    : `\n[结论] FAIL（${failed} 条路由未通过，${probeFailed} 项探针未通过）`,
);

try {
  fs.unlinkSync(outfile);
} catch {
  /* ignore */
}
process.exit(failed === 0 && errors.length === 0 && probeFailed === 0 ? 0 : 1);
