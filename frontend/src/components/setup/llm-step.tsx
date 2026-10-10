import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { configApi } from '@/api/client';
import type { ConnectionTestResult, LlmConfigInput, LlmProvider } from '@/api/types';
import { toast } from '@/stores/ui';
import { Field } from '@/components/common/field';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ERROR_CLASS_FIX, PROVIDERS } from './constants';
import { Cloud, Sparkles, CircleCheck, CircleX, ArrowLeft, ArrowRight } from '@/components/icons';

/** 步骤 2：接入模型后端（选服务商 → 填端点/Key/模型 → 测试连接 → 设为默认） */
export function LlmStep({ onBack, onSaved }: { onBack: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<LlmConfigInput>({
    provider: 'deepseek',
    base_url: 'https://api.deepseek.com/v1',
    api_key: '',
    model: 'deepseek-chat',
    context_window: 8192,
  });
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);

  const testConn = useMutation({
    mutationFn: () => configApi.testLlm(form),
    onSuccess: (res) => setTestResult(res),
    onError: () => setTestResult(null),
  });

  const saveLlm = useMutation({
    mutationFn: () => configApi.setLlm(form),
    onSuccess: () => {
      toast.success('模型后端已设为默认', '接下来安装示例内容，就能直接开一场会话了。');
      onSaved();
    },
    onError: () => toast.danger('保存失败', '后端拒绝了这次配置，检查字段后重试。'),
  });

  const applyProvider = (provider: LlmProvider) => {
    const preset = PROVIDERS.find((p) => p.value === provider);
    setForm((f) => ({ ...f, provider, base_url: preset?.defaultUrl ?? f.base_url }));
    setTestResult(null);
  };

  const canSave = testResult?.ok === true;

  return (
    <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
      <h2 className="title-section flex items-center gap-2 text-fg">
        <Cloud className="size-4 text-muted" aria-hidden="true" />
        接入模型后端
      </h2>
      <p className="text-sm leading-relaxed text-muted">
        v1 只维护<strong className="font-medium text-fg-2">一个</strong>默认后端。密钥加密存库，
        不会进 git，也不会回显。
      </p>

      <Field label="服务商" htmlFor="provider" hint="选完会自动填好端点地址，你只需要替换 Key 和模型名。">
        <Select value={form.provider} onValueChange={(v) => applyProvider(v as LlmProvider)}>
          <SelectTrigger id="provider">
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
        htmlFor="base-url"
        hint={PROVIDERS.find((p) => p.value === form.provider)?.hint}
      >
        <Input
          id="base-url"
          value={form.base_url}
          onChange={(e) => {
            setForm((f) => ({ ...f, base_url: e.target.value }));
            setTestResult(null);
          }}
          spellCheck={false}
          className="font-mono text-sm"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="API Key" htmlFor="api-key" optional={form.provider === 'ollama'} hint="本机 Ollama 通常不需要。">
          <Input
            id="api-key"
            type="password"
            value={form.api_key ?? ''}
            onChange={(e) => {
              setForm((f) => ({ ...f, api_key: e.target.value }));
              setTestResult(null);
            }}
            placeholder="sk-..."
            autoComplete="off"
            className="font-mono text-sm"
          />
        </Field>
        <Field label="模型名" htmlFor="model" hint="写服务商文档里的准确 ID，例如 deepseek-chat。">
          <Input
            id="model"
            value={form.model}
            onChange={(e) => {
              setForm((f) => ({ ...f, model: e.target.value }));
              setTestResult(null);
            }}
            spellCheck={false}
            className="font-mono text-sm"
          />
        </Field>
      </div>

      <Field
        label="上下文窗口（token）"
        htmlFor="ctx"
        hint="默认 8192。显存紧或按量计费时不要盲目拉满——KV Cache 会随上下文线性增长。"
      >
        <Input
          id="ctx"
          type="number"
          min={1024}
          max={131072}
          step={1024}
          value={form.context_window ?? 8192}
          onChange={(e) => setForm((f) => ({ ...f, context_window: Number(e.target.value) }))}
        />
      </Field>

      {testResult ? (
        <div
          role="status"
          className={cn(
            'space-y-2 rounded-md border border-border p-3',
            testResult.ok ? 'bg-success-subtle' : 'bg-danger-subtle',
          )}
        >
          <p className="flex items-center gap-2 text-base font-medium text-fg">
            {testResult.ok ? (
              <CircleCheck className="size-4 text-success" aria-hidden="true" />
            ) : (
              <CircleX className="size-4 text-danger" aria-hidden="true" />
            )}
            {testResult.ok ? '连接成功' : '连接失败'}
            <span className="tech-meta font-normal">耗时 {testResult.latency_ms}ms</span>
          </p>
          <p className="text-sm leading-relaxed text-fg-2">{testResult.message}</p>
          {!testResult.ok && testResult.error_class ? (
            <p className="text-sm leading-relaxed text-fg-2">
              <span className="font-medium">怎么修：</span>
              {ERROR_CLASS_FIX[testResult.error_class]}
            </p>
          ) : null}
          {testResult.model_seen ? (
            <p className="tech-meta">服务端实际看到的模型名：{testResult.model_seen}</p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          上一步
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => testConn.mutate()}
            loading={testConn.isPending}
            disabled={!form.base_url || !form.model}
          >
            <Sparkles className="size-4" aria-hidden="true" />
            测试连接
          </Button>
          <Button
            variant="primary"
            onClick={() => saveLlm.mutate()}
            loading={saveLlm.isPending}
            disabled={!canSave}
          >
            设为默认并继续
            <ArrowRight className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
      {!canSave ? (
        <p className="text-sm text-meta">先点「测试连接」，通过之后才能设为默认。</p>
      ) : null}
    </section>
  );
}
