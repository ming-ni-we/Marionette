import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { emptyPresetData, presetsApi } from '@/api/client';
import type { PresetData } from '@/api/types';
import { SAMPLE_PRESETS } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';
import { ErrorState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  BaseInfoSection,
  BudgetSection,
  ImageHookSection,
  MemorySection,
  PromptSection,
  SamplingSection,
} from '@/components/preset/preset-sections';
import { SlidersHorizontal, Save, CircleCheck, TriangleAlert, ArrowLeft, Coins, Info } from '@/components/icons';

/** 预设编辑器（SPEC §7）：系统提示词 · 采样参数 · 上下文预算 · 记忆 · 出图钩子 */
export function PresetEditorPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  // 路由 /presets/new 命中静态段后 useParams() 为空 → id=''，同样视为新建
  const isNew = !id || id === 'new';

  const query = useQuery({
    queryKey: ['preset', id],
    queryFn: () => presetsApi.get(id),
    enabled: !isNew,
    retry: false,
  });

  const demoPreset = !isNew ? SAMPLE_PRESETS.find((p) => p.id === id) : undefined;
  const offline = query.isError;

  const [draft, setDraft] = useState<PresetData>(emptyPresetData);
  const [dirty, setDirty] = useState(false);
  const loadedRef = useRef<string | null>(null);

  useEffect(() => {
    const source = query.data?.data ?? (offline ? demoPreset?.data : undefined);
    const key = query.data?.id ?? (offline && demoPreset ? demoPreset.id : null);
    if (source && key && loadedRef.current !== key) {
      setDraft(source);
      setDirty(false);
      loadedRef.current = key;
    }
  }, [query.data, offline, demoPreset]);

  useEffect(() => {
    if (isNew) {
      setDraft(emptyPresetData());
      setDirty(false);
      loadedRef.current = 'new';
    }
  }, [isNew]);

  const patch = (p: Partial<PresetData>) => {
    setDraft((d) => ({ ...d, ...p }));
    setDirty(true);
  };

  const save = useMutation({
    mutationFn: () => {
      const payload = { spec: 'rpg_preset' as const, spec_version: '1.0', data: draft };
      return isNew ? presetsApi.create(payload) : presetsApi.update(id, payload);
    },
    onSuccess: (preset) => {
      setDirty(false);
      toast.success(isNew ? '预设已创建' : '已保存');
      void qc.invalidateQueries({ queryKey: ['presets'] });
      if (isNew) navigate(`/presets/${preset.id}`, { replace: true });
    },
    onError: () => toast.danger('保存失败', '后端拒绝了这次写入。'),
  });

  if (!isNew && query.isError && !demoPreset) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-10">
        <ErrorState
          description={`没找到这套预设（id: ${id}）。它可能已被删除。`}
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link to="/">回到内容库</Link>
              </Button>
              <Button variant="ghost" asChild>
                <Link to="/presets/new">新建预设</Link>
              </Button>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-sticky flex flex-wrap items-center gap-3 border-b border-border bg-surface/95 px-6 py-2.5 backdrop-blur-[2px]">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/">
            <ArrowLeft className="size-4" aria-hidden="true" />
            内容库
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="size-4 text-muted" aria-hidden="true" />
          <span className="text-md font-medium text-fg">{draft.name || '未命名预设'}</span>
        </div>
        <Badge variant="outline">P1 · 参数编辑</Badge>
        {isNew ? <Badge variant="accent">新建</Badge> : null}
        {offline && demoPreset ? <Badge variant="warn">演示数据</Badge> : null}
        <span
          className={cn('inline-flex items-center gap-1.5 text-sm', dirty ? 'text-warn' : 'text-muted')}
          aria-live="polite"
        >
          {dirty ? (
            <>
              <TriangleAlert className="size-3.5" aria-hidden="true" />
              有未保存修改
            </>
          ) : (
            <>
              <CircleCheck className="size-3.5" aria-hidden="true" />
              已保存
            </>
          )}
        </span>
        <span className="tech-meta ml-auto flex items-center gap-1.5">
          <Coins className="size-3.5" aria-hidden="true" />
          {draft.context_budget.max_context_tokens} ctx
        </span>
        <Button variant="primary" size="sm" onClick={() => save.mutate()} loading={save.isPending}>
          <Save className="size-4" aria-hidden="true" />
          保存
        </Button>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-2xl px-6 py-4">
          <p className="mb-3 flex items-start gap-2 rounded-md border border-border bg-surface-warm px-3 py-2 text-sm leading-relaxed text-muted">
            <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden="true" />
            预设决定「模型怎么说话」和「上下文预算怎么分」。开会话时会挑一套默认预设 ——
            改错了不会毁数据，重新选一套即可。
          </p>

          <div>
            <BaseInfoSection draft={draft} patch={patch} />
            <PromptSection draft={draft} patch={patch} />
            <SamplingSection draft={draft} patch={patch} />
            <BudgetSection draft={draft} patch={patch} />
            <MemorySection draft={draft} patch={patch} />
            <ImageHookSection draft={draft} patch={patch} />
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
