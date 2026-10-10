import { useQuery } from '@tanstack/react-query';
import { systemApi } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Database, RefreshCw, TriangleAlert, CircleCheck, CircleX, Info, ArrowRight } from '@/components/icons';

/** 步骤 1：环境自检（数据库 / 扩展 / 端口） */
export function SelfCheckStep({ onNext }: { onNext: () => void }) {
  const selfcheck = useQuery({
    queryKey: ['system', 'selfcheck'],
    queryFn: systemApi.selfcheck,
    retry: false,
  });

  return (
    <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="title-section flex items-center gap-2 text-fg">
          <Database className="size-4 text-muted" aria-hidden="true" />
          环境自检
        </h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void selfcheck.refetch()}
          loading={selfcheck.isFetching}
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          重新检测
        </Button>
      </div>

      {selfcheck.isLoading ? (
        <p className="text-base text-muted">正在检测…</p>
      ) : selfcheck.isError ? (
        <div className="space-y-3 rounded-md border border-border bg-warn-subtle p-3">
          <p className="flex items-start gap-2 text-base leading-relaxed text-fg">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden="true" />
            <span>
              连不上后端实例。确认云服务器上已经跑起 <code className="font-mono">docker compose up -d</code>，
              并且三个容器都 healthy。
            </span>
          </p>
          <p className="text-sm text-muted">
            这一步过不去也不影响你先配模型——可以点「下一步」继续，稍后在设置里重跑自检。
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-border-soft">
          {(selfcheck.data?.checks ?? []).map((c) => (
            <li key={c.name} className="flex items-start gap-3 py-2.5">
              {c.status === 'ok' ? (
                <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
              ) : c.status === 'warn' ? (
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden="true" />
              ) : (
                <CircleX className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-fg">{c.name}</span>
                  <Badge variant={c.status === 'ok' ? 'success' : c.status === 'warn' ? 'warn' : 'danger'}>
                    {c.status === 'ok' ? '正常' : c.status === 'warn' ? '注意' : '失败'}
                  </Badge>
                </div>
                <p className="mt-0.5 text-sm leading-relaxed text-muted">{c.detail}</p>
                {c.status !== 'ok' && c.fix_hint ? (
                  <p className="mt-1 flex items-start gap-1.5 text-sm leading-relaxed text-fg-2">
                    <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden="true" />
                    {c.fix_hint}
                  </p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {selfcheck.data?.port_in_use ? (
        <p className="text-sm leading-relaxed text-warn">
          检测到端口被占用，建议改用 {selfcheck.data?.suggested_port}。
        </p>
      ) : null}

      <div className="flex justify-end">
        <Button
          variant="primary"
          onClick={onNext}
          disabled={!selfcheck.isSuccess && !selfcheck.isError}
        >
          下一步：接入模型
          <ArrowRight className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </section>
  );
}
