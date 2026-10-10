import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { systemApi } from '@/api/client';
import { Hint } from '@/components/ui/tooltip';
import { Cpu, HardDrive, Plug, TriangleAlert } from '@/components/icons';

type StatusTone = 'ok' | 'warn' | 'fail' | 'unknown';

const DOT_CLASS: Record<StatusTone, string> = {
  ok: 'bg-success',
  warn: 'bg-warn',
  fail: 'bg-danger',
  unknown: 'bg-meta',
};

function StatusDot({ tone, label }: { tone: StatusTone; label: string }) {
  return (
    <span className="relative flex size-2.5 shrink-0" role="img" aria-label={label}>
      <span className={cn('size-2.5 rounded-full', DOT_CLASS[tone])} />
    </span>
  );
}

/**
 * 本机状态位：模型连接状态 / 后端 / 存储路径。
 * 替代账号位（单机无账号体系）。未连后端时给出直达首启向导的引导，不留空白。
 */
export function InstanceStatus({ expanded }: { expanded: boolean }) {
  const info = useQuery({
    queryKey: ['system', 'info'],
    queryFn: systemApi.info,
    retry: false,
    staleTime: 30_000,
  });

  const connected = info.isSuccess;
  const tone: StatusTone = info.isLoading ? 'unknown' : connected ? 'ok' : 'fail';
  const summary = info.isLoading
    ? '检测中…'
    : connected
      ? `${info.data.llm_provider} · ${info.data.llm_model}`
      : '未连后端';

  const title = info.isLoading
    ? '正在检测实例状态'
    : connected
      ? `模型 ${info.data.llm_model}（${info.data.llm_provider}）· 出图 ${info.data.image_provider}`
      : '未连接到后端实例';

  if (!expanded) {
    return (
      <Hint label={title} side="right">
        <div className="grid h-9 place-items-center">
          {connected ? (
            <StatusDot tone={tone} label={title} />
          ) : (
            <TriangleAlert className="size-4 text-warn" aria-hidden="true" />
          )}
        </div>
      </Hint>
    );
  }

  if (info.isLoading) {
    return (
      <div className="space-y-1.5 px-2 py-1.5">
        <div className="h-3 w-24 animate-pulse rounded-xs bg-surface-warm" aria-hidden="true" />
        <div className="h-3 w-32 animate-pulse rounded-xs bg-surface-warm" aria-hidden="true" />
        <span className="sr-only">正在检测实例状态</span>
      </div>
    );
  }

  if (!connected) {
    return (
      <Link
        to="/setup"
        className="block rounded-sm px-2 py-1.5 motion-fast hover:bg-surface-warm"
        aria-label="后端未连接，前往首启向导配置"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-warn">
          <TriangleAlert className="size-3.5 shrink-0" aria-hidden="true" />
          未连后端
        </span>
        <span className="mt-0.5 block text-xs leading-relaxed text-muted">
          去首启向导填后端地址并测试连接
        </span>
      </Link>
    );
  }

  return (
    <div className="space-y-1.5 px-2 py-1.5">
      <div className="flex items-center gap-2">
        <StatusDot tone={tone} label="模型连接正常" />
        <Cpu className="size-3.5 shrink-0 text-muted" aria-hidden="true" />
        <span className="min-w-0 truncate font-mono text-xs tabular-nums text-fg-2">
          {info.data.llm_model}
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs text-meta">
        <Plug className="size-3.5 shrink-0" aria-hidden="true" />
        <span className="truncate">{info.data.llm_provider}</span>
      </div>
      <div className="flex items-center gap-2 text-xs text-meta">
        <HardDrive className="size-3.5 shrink-0" aria-hidden="true" />
        <span className="truncate">v{info.data.app_version} · 本地存储</span>
      </div>
      <span className="sr-only">{summary}</span>
    </div>
  );
}
