import { StrictMode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { App } from '@/App';
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
