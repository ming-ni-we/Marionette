import { StrictMode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { App } from '@/App';
import { sessionHref } from '@/pages/session-list';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Toaster } from '@/components/ui/toast';

/**
 * 冒烟测试入口（仅供 scripts/smoke.mjs 使用，不参与生产构建）。
 * 与 main.tsx 使用同一套 Provider，唯一差别：用 MemoryRouter 以便按路径挂载。
 */
export function mount(path: string): Root {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  const container = document.getElementById('root');
  if (!container) throw new Error('缺少 #root');
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <TooltipProvider delayDuration={0}>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
  return root;
}

/**
 * 差异化视觉点的运行时探针（仅供 smoke.mjs 调用）：
 * 把 SSE 事件链路与三态命中判定从页面里抽出来直接跑一遍，证明逻辑真的成立。
 */
export { mockStream, mockStoryStream, mockWorldBookTest, SAMPLE_WORLDBOOKS } from '@/mocks/fixtures';

/**
 * 会话列表的剧情集成探针（S13 回归守卫，S14 验收）。
 *
 * 为什么必须驱动**真实页面**而不是复制一份判定逻辑：
 * 离线演示数据与真实后端数据的形状不同（真实数据里 `world_id` 一定存在，
 * 演示数据靠 `spec` 判定），只测离线路径会漏掉「世界观标题查不到 →
 * 退化成裸 UUID」这类只在联调时暴露的 bug。
 *
 * 检查四件事：
 *   1. 剧情会话与 1v1 会话在同一列表里**都出现**；
 *   2. 剧情条目带「剧情」标识；
 *   3. 剧情条目**链接指向 /stories/:id**，1v1 指向 /sessions/:id；
 *   4. 剧情条目标题显示所属世界观名，不是裸 id。
 */
export async function probeSessionList(): Promise<{
  rows: Array<{ isStory: boolean; title: string }>;
  hasStory: boolean;
  hasRpg: boolean;
  storyBadgeCount: number;
  storyTitleShowsWorld: boolean;
  storyHrefOk: boolean;
  rpgHrefOk: boolean;
}> {
  const container = document.getElementById('root');
  if (!container) throw new Error('缺少 #root');

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <TooltipProvider delayDuration={0}>
          <MemoryRouter initialEntries={['/sessions']}>
            <App />
          </MemoryRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  );

  await new Promise((r) => setTimeout(r, 500));

  // 列表项是 <li> 内含 <button onClick={navigate(...)}>，没有 <a href>。
  // 因此按 <li> 读条目，跳转分派改由直接调 sessionHref 验证。
  const items = Array.from(container.querySelectorAll('li')).filter((li) =>
    li.querySelector('button'),
  );
  const rows: Array<{ isStory: boolean; title: string }> = [];
  for (const li of items) {
    const text = (li.textContent || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    rows.push({ isStory: /剧情/.test(text), title: text });
  }

  const bodyText = (container.textContent || '').replace(/\s+/g, ' ');
  const storyBadgeCount = (bodyText.match(/\u5267\u60c5/g) || []).length;

  // 标题退化成裸 UUID 视为失败
  const looksLikeUuid = (s: string) => /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(s);
  const storyTitleShowsWorld =
    rows.some((r) => r.isStory) && rows.filter((r) => r.isStory).every((r) => !looksLikeUuid(r.title));

  // 直接验证分派的正确性（导出函数，无需 DOM）
  const storyHrefOk =
    sessionHref({ id: 'x1', spec: 'story_session' }) === '/stories/x1' &&
    sessionHref({ id: 'x2', spec: 'rpg_session', world_id: null }) === '/sessions/x2';
  // 兜底分支：spec 缺失但有 world_id，仍应按剧情处理
  const rpgHrefOk = sessionHref({ id: 'x3', spec: '', world_id: 'w-1' }) === '/stories/x3';

  return {
    rows,
    hasStory: rows.some((r) => r.isStory),
    hasRpg: rows.some((r) => !r.isStory),
    storyBadgeCount,
    storyTitleShowsWorld,
    storyHrefOk,
    rpgHrefOk,
  };
}

/**
 * 剧情演出页的多角色渲染回归探针。
 *
 * 它解决的是一类**离线路径永远抓不到**的 bug：后端对**第一个**说话者不发
 * `speaker_switch`（`chat.py` 的 `if index > 0:`），只发 `delta + speaker_id`。
 * 若前端 `appendDelta` 在匹配不到 `speaker_id` 时退回「最后一条 assistant」，
 * 该说话者的台词就会被写进前一条消息——通常是导演的旁白——于是
 * 「旁白气泡里长出角色台词，而该角色没有自己的气泡」。
 *
 * 因此这里必须驱动**真实的 `StoryRuntimePage`**（而不是复制一份逻辑），
 * 让它消费 `mockStoryStream` 的真实事件序列，再检查 DOM 里到底渲染出几条气泡。
 */
export async function probeStoryRuntime(): Promise<{
  ok: boolean;
  narrationClean: boolean;
  bubbles: Array<{ name: string; text: string }>;
  narrationText: string;
  suggestionCount: number;
  hasDirector: boolean;
  hasNode: boolean;
}> {
  const container = document.getElementById('root');
  if (!container) throw new Error('缺少 #root');

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <TooltipProvider delayDuration={0}>
          <MemoryRouter initialEntries={['/stories/s1f0a1e2-0002-4d02-9c02-000000000002']}>
            <App />
          </MemoryRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  );

  // 等首屏 query 走完离线兜底 + 挂载完成
  await new Promise((r) => setTimeout(r, 400));

  // 点「发送」触发一轮剧情：直接把 mockStoryStream 接进页面的流式状态机
  const textarea = container.querySelector<HTMLTextAreaElement>('textarea[aria-label="输入你的行动"]');
  if (!textarea) throw new Error('剧情页没有渲染出行动输入框');
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    'value',
  )?.set;
  setter?.call(textarea, '我推门进去，把伞立在门边。');
  textarea.dispatchEvent(new window.Event('input', { bubbles: true }));

  await new Promise((r) => setTimeout(r, 80));
  const sendBtn = container.querySelector<HTMLButtonElement>('button[aria-label="发送你的行动"]');
  if (!sendBtn) throw new Error('剧情页没有渲染出发送按钮');
  sendBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));

  // 等 mockStoryStream 整条链路跑完（≈ t+280ms，留足余量）
  await new Promise((r) => setTimeout(r, 3600));

  /* ---- 读 DOM：按「角色名 + 正文」抽取气泡 ---- */
  const articles = Array.from(container.querySelectorAll('article[aria-label$="的消息"]'));
  const bubbles: Array<{ name: string; text: string }> = [];
  for (const a of articles) {
    const name = a.querySelector('span.font-medium')?.textContent?.trim() || '';
    const body = a.querySelector('p.narrative')?.textContent?.trim() || '';
    const isUser = a.getAttribute('aria-label') === '你的消息';
    if (isUser) continue;
    if (body) bubbles.push({ name, text: body });
  }

  // 旁白块（居中、无角色头）
  const narrationEl = container.querySelector('div[aria-label="旁白"] p.narrative');
  const narrationText = narrationEl?.textContent?.trim() || '';

  const suggestionCount = container.querySelectorAll('button[aria-label], button').length;
  const suggestionButtons = Array.from(
    container.querySelectorAll('[aria-label="行动建议"] button'),
  ).length;

  const bodyText = container.textContent || '';

  const su = bubbles.find((b) => b.name === '苏晚');
  const zhou = bubbles.find((b) => b.name === '老周');
  const narrationClean = narrationText.includes('雨下了三天') && !narrationText.includes('雨大，伞搁门口');

  return {
    ok:
      bubbles.length >= 2 &&
      Boolean(su?.text.includes('雨大，伞搁门口')) &&
      Boolean(zhou?.text.includes('公告你看了没有')) &&
      narrationClean &&
      suggestionButtons >= 3 &&
      /导演|在场|第 2 轮/.test(bodyText),
    narrationClean,
    bubbles,
    narrationText,
    suggestionCount: suggestionButtons || suggestionCount,
    hasDirector: /导演/.test(bodyText),
    hasNode: /雨夜的第一封信/.test(bodyText),
  };
}

/**
 * 剧情**多轮**顺序探针（回归守卫：回复跑到用户消息上方）。
 *
 * 复现的真实故障：同一个角色每轮都在场、`speaker_id` 恒定，
 * 若 `appendDelta` 反查气泡时不限定「本轮」范围，第二轮回复会被
 * 追加进**第一轮**那条气泡里 —— 而它在 DOM 里位于用户消息**上方**，
 * 于是看起来「我回答完，角色的话跑到我问题前面去了」。
 *
 * 因此在真实页面里连发两轮，然后按 DOM 顺序断言：
 *   「第二轮的用户消息」必须出现在「第二轮的回复」**之前**。
 */
export async function probeStoryMultiTurn(): Promise<{
  ok: boolean;
  order: string[];
  secondUserIdx: number;
  secondReplyIdx: number;
  firstTurnReplyGrew: boolean;
}> {
  const container = document.getElementById('root');
  if (!container) throw new Error('缺少 #root');

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <TooltipProvider delayDuration={0}>
          <MemoryRouter initialEntries={['/stories/s1f0a1e2-0003-4d03-9c03-000000000003']}>
            <App />
          </MemoryRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
  await new Promise((r) => setTimeout(r, 400));

  const typeAndSend = async (text: string) => {
    const textarea = container.querySelector<HTMLTextAreaElement>('textarea[aria-label="输入你的行动"]');
    if (!textarea) throw new Error('剧情页没有渲染出行动输入框');
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
    setter?.call(textarea, text);
    textarea.dispatchEvent(new window.Event('input', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 80));
    const btn = container.querySelector<HTMLButtonElement>('button[aria-label="发送你的行动"]');
    if (!btn) throw new Error('剧情页没有渲染出发送按钮');
    btn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  };

  /* ---- 第 1 轮 ---- */
  await typeAndSend('第一轮：我推门进去。');
  await new Promise((r) => setTimeout(r, 3800));
  // 记下第一轮里苏晚气泡的正文长度
  const firstTurnSuLen =
    Array.from(container.querySelectorAll('article[aria-label$="的消息"]'))
      .filter((a) => a.querySelector('span.font-medium')?.textContent?.trim() === '苏晚')
      .map((a) => (a.querySelector('p.narrative')?.textContent || '').length)
      .reduce((a, b) => Math.max(a, b), 0);

  /* ---- 第 2 轮 ---- */
  await typeAndSend('第二轮：我走到柜台前。');
  await new Promise((r) => setTimeout(r, 3800));

  /* ---- 按 DOM 顺序抽取所有消息，定位第二轮用户消息与紧随其后的回复 ---- */
  const nodes = Array.from(container.querySelectorAll('article[aria-label$="的消息"]'));
  const order: string[] = [];
  let secondUserIdx = -1;
  let secondReplyIdx = -1;

  /** 用户气泡没有 `p.narrative`（那是角色正文的类名），退化为取整块文本。 */
  const readBody = (a: Element, isUser: boolean) => {
    if (!isUser) return (a.querySelector('p.narrative')?.textContent || '').trim();
    // 用户气泡：取除头像位（aria-hidden）与操作按钮外的文本
    const text = (a.textContent || '').trim();
    return text.replace(/^你/, '').trim();
  };

  nodes.forEach((a, idx) => {
    const label = a.getAttribute('aria-label') || '';
    const isUser = label === '你的消息';
    const name = a.querySelector('span.font-medium')?.textContent?.trim() || '';
    const body = readBody(a, isUser);
    order.push(isUser ? `user:${body.slice(0, 10)}` : `${name}:${body.slice(0, 10)}`);
    if (isUser && body.includes('第二轮')) secondUserIdx = idx;
    if (!isUser && secondUserIdx >= 0 && secondReplyIdx < 0 && body) secondReplyIdx = idx;
  });

  // 第一轮的苏晚气泡是否被第二轮内容「撑大」（说明误命中）
  const agoraSuLen =
    Array.from(container.querySelectorAll('article[aria-label$="的消息"]'))
      .filter((a) => a.querySelector('span.font-medium')?.textContent?.trim() === '苏晚')
      .map((a) => (a.querySelector('p.narrative')?.textContent || '').length)
      .reduce((a, b) => Math.max(a, b), 0);

  // 判定两条**同时**成立才算通过：
  //   1. 第二轮的用户消息出现在它之后的回复**之前**（顺序对）；
  //   2. 第一轮的旧气泡**没有**被第二轮内容撑大（没有误命中）。
  // 第 2 条才是真正的回归信号 —— 顺序可能「看起来对」（第二轮确实新建了气泡），
  // 但同时内容又被灌进了历史气泡，DOM 顺序断言单独看不出来。
  const firstTurnReplyGrew = agoraSuLen > firstTurnSuLen + 30;
  const ok = secondUserIdx >= 0 && secondReplyIdx > secondUserIdx && !firstTurnReplyGrew;

  return {
    ok,
    order,
    secondUserIdx,
    secondReplyIdx,
    firstTurnReplyGrew,
  };
}

/**
 * S15-2 探针：建议芯片的**单击预填 / 直发**两种交互。
 *
 * 为什么必须用真实 DOM 驱动：这里守的是「芯片被点之后**没有**立刻发出去」——
 * 一个纯逻辑层的断言看不出来（`onSend` 有没有被调用，取决于事件接线）。
 *
 * 三种交互分别断言：
 *   1. 单击主体 → 输入框被预填，且**没有**产生新一轮（消息数不变、state 仍 idle）
 *   2. 点 ➤ 直发 → 立即发出（消息数增加）
 *   3. 双击主体 → 也走直发
 */
export async function probeSuggestionChip(): Promise<{
  ok: boolean;
  prefilled: string;
  sentAfterPick: boolean;
  sentAfterZap: boolean;
  sentAfterDblClick: boolean;
  chipCount: number;
}> {
  const container = document.getElementById('root');
  if (!container) throw new Error('缺少 #root');

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <TooltipProvider delayDuration={0}>
          <MemoryRouter initialEntries={['/stories/s1f0a1e2-0002-4d02-9c02-000000000002']}>
            <App />
          </MemoryRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  );

  await new Promise((r) => setTimeout(r, 400));

  const textarea = container.querySelector<HTMLTextAreaElement>(
    'textarea[aria-label="输入你的行动"]',
  );
  if (!textarea) throw new Error('剧情页没有渲染出行动输入框');
  const sendBtn = container.querySelector<HTMLButtonElement>('button[aria-label="发送你的行动"]');

  // 先跑一轮，让建议芯片出现（建议由 mock 在 done 前下发）
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    'value',
  )?.set;
  setter?.call(textarea, '我先不出声，听着。');
  textarea.dispatchEvent(new window.Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 60));
  sendBtn?.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 3600));

  const group = container.querySelector('[aria-label="行动建议"]');
  const chips = group ? Array.from(group.querySelectorAll('button')) : [];
  // 每张芯片 = 主体按钮 + ➤ 直发按钮 → 主体数 = 总数 / 2
  const mainChips = chips.filter((b) => !b.getAttribute('aria-label')?.startsWith('直接发送'));

  const userMsgCount = () =>
    container.querySelectorAll('article[aria-label="你的消息"]').length;
  const beforePick = userMsgCount();

  // ---- 1. 单击主体 → 预填，不发送 ----
  let prefilled = '';
  mainChips[0]?.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 80));
  prefilled = textarea.value;
  const sentAfterPick = userMsgCount() > beforePick;

  // ---- 2. 点 ➤ 直发 ----
  const zap = chips.find((b) =>
    b.getAttribute('aria-label')?.startsWith('直接发送'),
  ) as HTMLButtonElement | undefined;
  zap?.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 200));
  const sentAfterZap = userMsgCount() > beforePick;

  // 等这轮跑完，芯片重新出现
  await new Promise((r) => setTimeout(r, 3600));
  const beforeDbl = userMsgCount();
  const group2 = container.querySelector('[aria-label="行动建议"]');
  const chips2 = group2
    ? Array.from(group2.querySelectorAll('button')).filter(
        (b) => !b.getAttribute('aria-label')?.startsWith('直接发送'),
      )
    : [];

  // ---- 3. 双击主体 → 直发 ----
  chips2[0]?.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 200));
  const sentAfterDblClick = userMsgCount() > beforeDbl;

  return {
    ok:
      mainChips.length >= 3 &&
      prefilled.trim().length > 0 &&
      sentAfterPick === false &&
      sentAfterZap === true &&
      sentAfterDblClick === true,
    prefilled,
    sentAfterPick,
    sentAfterZap,
    sentAfterDblClick,
    chipCount: mainChips.length,
  };
}

/**
 * 剧情配图探针（S16 步骤 8）。
 *
 * 断言四件事，覆盖「图会不会出现」「图注对不对」「点击能不能放大」「放大后能不能关」：
 *   1. `image` 事件到达后，对话流里出现配图块（`figure[data-scene-image]`）
 *   2. 图注是中文语义文案（角色登场 / 剧情节点 / 手动绘制），不是裸 reason 值
 *   3. 图片 src 指向资产内容端点（`/assets/<id>/content`）
 *   4. 点击图片弹出灯箱（`role="dialog"`），按 Esc 能关掉
 *
 * 注意 jsdom **不会真正加载图片**，所以 `onError` 不会触发、占位分支不会走到 ——
 * 这是刻意的：本探针只验证「接线对不对」，占位样式靠人工/视觉验收。
 */
export async function probeSceneImage(): Promise<{
  ok: boolean;
  figureCount: number;
  caption: string;
  srcOk: boolean;
  openedDialog: boolean;
  closedByEsc: boolean;
}> {
  const container = document.getElementById('root');
  if (!container) throw new Error('缺少 #root');

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  const root = createRoot(container);
  root.render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <TooltipProvider delayDuration={0}>
          <MemoryRouter initialEntries={['/stories/s1f0a1e2-0002-4d02-9c02-000000000002']}>
            <App />
          </MemoryRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  );

  await new Promise((r) => setTimeout(r, 400));

  const textarea = container.querySelector<HTMLTextAreaElement>(
    'textarea[aria-label="输入你的行动"]',
  );
  const sendBtn = container.querySelector<HTMLButtonElement>('button[aria-label="发送你的行动"]');
  if (!textarea) throw new Error('剧情页没有渲染出行动输入框');

  // 跑一轮：mock 会在 usage 之后、actions 之前下发 image 事件
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    'value',
  )?.set;
  setter?.call(textarea, '我盯着那封信看。');
  textarea.dispatchEvent(new window.Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 60));
  sendBtn?.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 4200));

  const figures = Array.from(container.querySelectorAll<HTMLElement>('figure[data-scene-image]'));
  const caption = figures[0]?.querySelector('figcaption')?.textContent?.trim() ?? '';
  const img = figures[0]?.querySelector('img');
  const srcOk = Boolean(img?.getAttribute('src')?.includes('/assets/'));

  // ---- 点击放大：figure 内的按钮应打开灯箱 ----
  const zoomBtn = figures[0]?.querySelector<HTMLButtonElement>('button[aria-label^="放大查看"]');
  // Radix 用 pointerdown 触发（不是 click），jsdom 下必须按真实交互序列派发，
  // 否则「点得动」这件事没被真正验证。
  zoomBtn?.dispatchEvent(
    new window.PointerEvent('pointerdown', { bubbles: true, cancelable: true, button: 0 }),
  );
  zoomBtn?.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 260));
  // Dialog 走 Portal 渲染到 document.body，不能在 container 里找
  const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
  const openedDialog = Boolean(dialog);

  // ---- Esc 关闭（Radix Dialog 原生支持）----
  const esc = new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
  (dialog ?? document).dispatchEvent(esc);
  await new Promise((r) => setTimeout(r, 260));
  const closedByEsc = !document.querySelector('[role="dialog"]');

  const validCaptions = new Set(['角色登场', '剧情节点', '手动绘制']);

  return {
    ok:
      figures.length >= 1 &&
      validCaptions.has(caption) &&
      srcOk &&
      openedDialog &&
      closedByEsc,
    figureCount: figures.length,
    caption,
    srcOk,
    openedDialog,
    closedByEsc,
  };
}
