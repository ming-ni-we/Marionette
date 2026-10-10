import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { configApi } from '@/api/client';
import type { LlmConfigInput, LlmProvider } from '@/api/types';
import { toast } from '@/stores/ui';
import { Field } from '@/components/common/field';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { SettingsSection } from './section';
import { PROVIDERS, PROVIDER_LABEL } from './providers';
import { Cloud, CircleCheck, CircleX, TriangleAlert, LoaderCircle, RefreshCw } from '@/components/icons';

/** 模型后端：单后端 BYOK 配置 + 连接测试 + 保存 */
export function LlmSection() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['config', 'llm'],
    queryFn: configApi.getLlm,
    retry: false,
  });

  const [form, setForm] = useState<LlmConfigInput>({
    provider: 'deepseek',
    base_url: 'https://api.deepseek.com/v1',
    api_key: '',
    model: '',
    context_window: 8192,
  });
  const [dirty, setDirty] = useState(false);
  const [testOk, setTestOk] = useState(false);

  // 后端返回后回填（api_key 不回显，留空表示"继续沿用"）
  useEffect(() => {
    if (!data) return;
    setForm({
      provider: data.provider,
      base_url: data.base_url,
      api_key: '',
      model: data.model,
      context_window: data.context_window ?? 8192,
    });
    setTestOk(false);
    setDirty(false);
  }, [data]);

  const testConn = useMutation({
    mutationFn: () => configApi.testLlm(form),
    onSuccess: (res) => {
      setTestOk(res.ok);
      if (res.ok) {
        toast.success('连接成功', `耗时 ${res.latency_ms}ms，服务端看到的模型：${res.model_seen ?? form.model}`);
      } else {
        toast.danger('连接失败', res.message);
      }
    },
    onError: () => {
      setTestOk(false);
      toast.danger('测试请求未送达', '确认后端在线，再检查端点地址。');
    },
  });

  const save = useMutation({
    mutationFn: () => configApi.setLlm(form),
    onSuccess: () => {
      toast.success('模型后端已更新', '新会话会使用这份配置。');
      setDirty(false);
      setTestOk(false);
      void qc.invalidateQueries({ queryKey: ['config', 'llm'] });
      void qc.invalidateQueries({ queryKey: ['system', 'info'] });
    },
    onError: () => toast.danger('保存失败', '后端拒绝了这份配置，检查字段后重试。'),
  });

  const patch = (p: Partial<LlmConfigInput>) => {
    setForm((f) => ({ ...f, ...p }));
    setDirty(true);
    setTestOk(false);
  };

  return (
    <SettingsSection
      icon={Cloud}
      title="模型后端"
      aside={
        isLoading ? (
          <span className="flex items-center gap-1.5 text-sm text-muted">
            <LoaderCircle className="size-3.5 animate-spin" aria-hidden="true" />
            读取中
          </span>
        ) : data ? (
          <span className="text-sm text-meta">
            当前：{PROVIDER_LABEL[data.provider]} ·{' '}
            <span className="font-mono">{data.model || '未设模型'}</span>
          </span>
        ) : (
          <Badge variant="warn">未连后端</Badge>
        )
      }
    >
      <p className="text-base leading-relaxed text-muted">
        v1 只维护一个默认后端。密钥加密存库、不回显、不进 git；这里留空表示沿用已保存的密钥。
      </p>

      <Field label="服务商" htmlFor="set-provider" hint="选完自动填端点地址，你只需替换 Key 与模型名。">
        <Select
          value={form.provider}
          onValueChange={(v) => {
            const p = v as LlmProvider;
            const preset = PROVIDERS.find((x) => x.value === p);
            patch({ provider: p, base_url: preset?.defaultUrl ?? form.base_url });
          }}
        >
          <SelectTrigger id="set-provider">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROVIDERS.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field
        label="端点地址（Base URL）"
        htmlFor="set-base-url"
        hint="OpenAI 兼容端点通常以 /v1 结尾；GLM 兼容端点是 /v4。"
      >
        <Input
          id="set-base-url"
          value={form.base_url}
          onChange={(e) => patch({ base_url: e.target.value })}
          spellCheck={false}
          className="font-mono text-sm"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="API Key"
          htmlFor="set-api-key"
          optional={form.provider === 'ollama'}
          hint={data ? '已保存密钥，留空即沿用；本机 Ollama 通常不需要。' : '本机 Ollama 通常不需要。'}
        >
          <Input
            id="set-api-key"
            type="password"
            value={form.api_key ?? ''}
            onChange={(e) => patch({ api_key: e.target.value })}
            placeholder={data ? '••••••••（留空不改）' : 'sk-...'}
            autoComplete="off"
            className="font-mono text-sm"
          />
        </Field>
        <Field label="模型名" htmlFor="set-model" hint="写服务商文档里的准确 ID，例如 deepseek-chat。">
          <Input
            id="set-model"
            value={form.model}
            onChange={(e) => patch({ model: e.target.value })}
            spellCheck={false}
            className="font-mono text-sm"
          />
        </Field>
      </div>

      <Field
        label="上下文窗口（token）"
        htmlFor="set-ctx"
        hint="默认 8192。显存紧或按量计费时不要盲目拉满——KV Cache 随上下文线性增长。"
      >
        <Input
          id="set-ctx"
          type="number"
          min={1024}
          max={131072}
          step={1024}
          value={form.context_window ?? 8192}
          onChange={(e) => patch({ context_window: Number(e.target.value) })}
          className="max-w-[12rem] font-mono text-sm tabular-nums"
        />
      </Field>

      {testConn.data && !testConn.data.ok ? (
        <div role="status" className="space-y-1.5 rounded-md border border-border bg-danger-subtle p-3">
          <p className="flex items-center gap-2 text-base font-medium text-fg">
            <CircleX className="size-4 text-danger" aria-hidden="true" />
            连接失败
            <span className="tech-meta font-normal">{testConn.data.error_class}</span>
          </p>
          <p className="text-sm leading-relaxed text-fg-2">{testConn.data.message}</p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 border-t border-border-soft pt-4">
        <Button
          variant="secondary"
          onClick={() => testConn.mutate()}
          loading={testConn.isPending}
          disabled={!form.base_url || !form.model}
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          测试连接
        </Button>
        <Button variant="primary" onClick={() => save.mutate()} loading={save.isPending} disabled={!dirty}>
          保存
        </Button>
        {dirty ? (
          <span className="flex items-center gap-1.5 text-sm text-warn">
            <TriangleAlert className="size-3.5" aria-hidden="true" />
            有未保存的改动
          </span>
        ) : testOk ? (
          <span className="flex items-center gap-1.5 text-sm text-success">
            <CircleCheck className="size-3.5" aria-hidden="true" />
            连接已验证
          </span>
        ) : null}
      </div>
    </SettingsSection>
  );
}
