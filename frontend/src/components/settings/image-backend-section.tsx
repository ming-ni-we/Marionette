import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { configApi, systemApi } from '@/api/client';
import { toast } from '@/stores/ui';
import { Field } from '@/components/common/field';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SettingsSection } from './section';
import { Images, CircleCheck, TriangleAlert, Cpu, HardDrive } from '@/components/icons';

/** 出图后端：provider 说明 + 本机 ComfyUI 连通性探测 */
export function ImageBackendSection() {
  const [baseUrl, setBaseUrl] = useState('http://host.docker.internal:8188');
  const info = useQuery({ queryKey: ['system', 'info'], queryFn: systemApi.info, retry: false });

  const probe = useMutation({
    mutationFn: () => configApi.probeComfyUI(baseUrl),
    onSuccess: (res) => {
      if (res.reachable) {
        toast.success(
          'ComfyUI 可达',
          `设备：${res.device ?? '未上报'} · checkpoint ${res.checkpoints.length} 个`,
        );
      } else {
        toast.warn('连不上 ComfyUI', '确认它已启动，且容器内能访问 host.docker.internal。');
      }
    },
    onError: () => toast.danger('探测请求未送达', '确认后端在线后再试。'),
  });

  return (
    <SettingsSection
      icon={Images}
      title="出图后端"
      aside={
        <span className="text-sm text-meta">
          当前：<span className="font-mono">{info.data?.image_provider ?? '未配置'}</span>
        </span>
      }
    >
      <p className="text-base leading-relaxed text-muted">
        出图走一条独立的 BYOK 通道：云端图像 API（<code className="font-mono text-sm">cloud</code>）或本机 ComfyUI（
        <code className="font-mono text-sm">local_comfyui</code>）。provider 由部署机{' '}
        <code className="font-mono text-sm">IMAGE_PROVIDER</code> 决定；这里主要用来探测本机 ComfyUI 是否就绪。
      </p>

      <div className="rounded-md border border-border bg-surface-warm p-3">
        <p className="flex items-start gap-2 text-sm leading-relaxed text-fg-2">
          <HardDrive className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden="true" />
          <span>
            ComfyUI 容器内访问宿主机服务必须用 <code className="font-mono">host.docker.internal</code>，不能用{' '}
            <code className="font-mono">127.0.0.1</code>——后者指向容器自己。默认端口 8188。
          </span>
        </p>
      </div>

      <Field label="ComfyUI 地址" htmlFor="set-comfy" hint="默认 http://host.docker.internal:8188。">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            id="set-comfy"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            spellCheck={false}
            className="min-w-[16rem] flex-1 font-mono text-sm"
          />
          <Button variant="secondary" onClick={() => probe.mutate()} loading={probe.isPending}>
            <Cpu className="size-4" aria-hidden="true" />
            探测
          </Button>
        </div>
      </Field>

      {probe.data ? (
        <div
          role="status"
          className={cn(
            'space-y-1 rounded-md border border-border p-3',
            probe.data.reachable ? 'bg-success-subtle' : 'bg-warn-subtle',
          )}
        >
          <p className="flex items-center gap-2 text-base font-medium text-fg">
            {probe.data.reachable ? (
              <CircleCheck className="size-4 text-success" aria-hidden="true" />
            ) : (
              <TriangleAlert className="size-4 text-warn" aria-hidden="true" />
            )}
            {probe.data.reachable ? 'ComfyUI 可达' : '无法连接'}
          </p>
          <p className="text-sm leading-relaxed text-fg-2">
            设备：<span className="font-mono">{probe.data.device ?? '未上报'}</span> · checkpoint：
            <span className="font-mono">{probe.data.checkpoints.length}</span> 个
          </p>
        </div>
      ) : null}
    </SettingsSection>
  );
}
