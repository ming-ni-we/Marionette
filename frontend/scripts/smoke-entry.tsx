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
export { mockStream, mockWorldBookTest, SAMPLE_WORLDBOOKS } from '@/mocks/fixtures';
