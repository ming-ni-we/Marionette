import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import './styles/globals.css';
import { App } from './App';
import { bootstrapUiPreferences } from './stores/ui';
import { TooltipProvider } from './components/ui/tooltip';
import { Toaster } from './components/ui/toast';

// 把持久化的主题 / 密度 / 阅读偏好同步到 <html>，避免首帧闪烁
bootstrapUiPreferences();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
});

const container = document.getElementById('root');
if (!container) {
  throw new Error('缺少 #root 挂载点');
}

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200} skipDelayDuration={300}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
);
