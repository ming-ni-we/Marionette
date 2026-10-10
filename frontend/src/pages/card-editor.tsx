import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { cardsApi, emptyCardData, ioApi } from '@/api/client';
import type { CardData } from '@/api/types';
import { SAMPLE_CARDS } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';
import { CardForm, CARD_GROUPS, type CardEditMode } from '@/components/cards/card-form';
import { CardPreview, estimateTokens } from '@/components/cards/card-preview';
import { NavList } from '@/components/common/group-section';
import { ErrorState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  UserRound,
  Save,
  CircleCheck,
  TriangleAlert,
  FileDown,
  ArrowLeft,
  MessageSquare,
  Coins,
} from '@/components/icons';

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function CardEditorPage() {
  const { cardId = '' } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const isNew = cardId === 'new';

  const query = useQuery({
    queryKey: ['card', cardId],
    queryFn: () => cardsApi.get(cardId),
    enabled: !isNew,
    retry: false,
  });

  // 后端不可达时，若命中内置示例 id 则用本地示例继续编辑（并在顶部标注）
  const demoCard = !isNew ? SAMPLE_CARDS.find((c) => c.id === cardId) : undefined;
  const offline = query.isError;

  const [draft, setDraft] = useState<CardData>(emptyCardData);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<CardEditMode>('quick');
  const [activeGroup, setActiveGroup] = useState<string>('base');
  const loadedRef = useRef<string | null>(null);
  const formRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const source = query.data?.data ?? (offline ? demoCard?.data : undefined);
    const key = query.data?.id ?? (offline && demoCard ? demoCard.id : null);
    if (source && key && loadedRef.current !== key) {
      setDraft(source);
      setDirty(false);
      loadedRef.current = key;
    }
  }, [query.data, offline, demoCard]);

  useEffect(() => {
    if (isNew) {
      setDraft(emptyCardData());
      setDirty(false);
      loadedRef.current = 'new';
    }
  }, [isNew]);

  const patch = (p: Partial<CardData>) => {
    setDraft((d) => ({ ...d, ...p }));
    setDirty(true);
  };

  const save = useMutation({
    mutationFn: async () => {
      const payload = { spec: 'rpg_card' as const, spec_version: '1.0', data: draft };
      return isNew ? cardsApi.create(payload) : cardsApi.update(cardId, payload);
    },
    onSuccess: (card) => {
      setDirty(false);
      toast.success(isNew ? '角色卡已创建' : '已保存', `「${card.data.name || '未命名'}」已写入内容库。`);
      void qc.invalidateQueries({ queryKey: ['cards'] });
      void qc.invalidateQueries({ queryKey: ['card', card.id] });
      if (isNew) navigate(`/cards/${card.id}`, { replace: true });
    },
    onError: () => toast.danger('保存失败', '后端拒绝了这次写入，稍后重试。'),
  });

  const totalTokens = useMemo(
    () =>
      estimateTokens(
        [
          draft.description,
          draft.personality,
          draft.scenario,
          draft.first_mes,
          draft.mes_example,
          draft.system_prompt,
          draft.post_history_instructions,
        ].join(''),
      ),
    [draft],
  );

  const gotoGroup = (id: string) => {
    setActiveGroup(id);
    const el = document.getElementById(`card-group-${id}`);
    el?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
  };

  if (!isNew && query.isError && !demoCard) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-10">
        <ErrorState
          description={`没找到这张角色卡（id: ${cardId}）。它可能已经被删除，或者当前后端实例换了数据库。`}
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link to="/">回到内容库</Link>
              </Button>
              <Button variant="ghost" asChild>
                <Link to="/cards/new">新建一张角色卡</Link>
              </Button>
            </>
          }
        />
      </div>
    );
  }

  if (!isNew && query.isLoading) {
    return (
      <div className="px-6 py-6">
        <div className="h-8 w-56 animate-pulse rounded-sm bg-surface-warm" aria-hidden="true" />
        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[220px_1fr_380px]">
          <div className="h-64 animate-pulse rounded-lg bg-surface-warm" aria-hidden="true" />
          <div className="h-96 animate-pulse rounded-lg bg-surface-warm" aria-hidden="true" />
          <div className="h-80 animate-pulse rounded-lg bg-surface-warm" aria-hidden="true" />
        </div>
        <span className="sr-only">正在加载角色卡</span>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col">
      {/* 顶部操作条：保存状态 / Token 估算 / 导出 / 试开会话 */}
      <header className="sticky top-0 z-sticky border-b border-border bg-surface/95 px-6 py-2.5 backdrop-blur-[2px]">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/">
              <ArrowLeft className="size-4" aria-hidden="true" />
              内容库
            </Link>
          </Button>

          <div className="flex items-center gap-2">
            <UserRound className="size-4 text-muted" aria-hidden="true" />
            <span className="text-md font-medium text-fg">{draft.name || '未命名角色卡'}</span>
          </div>

          {isNew ? <Badge variant="accent">新建</Badge> : null}
          {offline && demoCard ? <Badge variant="warn">演示数据</Badge> : null}

          <span
            className={cn(
              'inline-flex items-center gap-1.5 text-sm',
              dirty ? 'text-warn' : 'text-muted',
            )}
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
            约 {totalTokens} tok
          </span>

          <div className="flex items-center gap-2">
            <Tabs value={mode} onValueChange={(v) => setMode(v as CardEditMode)}>
              <TabsList>
                <TabsTrigger value="quick">快速</TabsTrigger>
                <TabsTrigger value="advanced">完整</TabsTrigger>
              </TabsList>
            </Tabs>

            {!isNew ? (
              <Button variant="outline" size="sm" asChild>
                <a href={ioApi.exportCardUrl(cardId)} download>
                  <FileDown className="size-4" aria-hidden="true" />
                  导出
                </a>
              </Button>
            ) : null}

            {!isNew ? (
              <Button variant="secondary" size="sm" asChild>
                <Link to={`/sessions?card=${cardId}`}>
                  <MessageSquare className="size-4" aria-hidden="true" />
                  试开一场会话
                </Link>
              </Button>
            ) : null}

            <Button
              variant="primary"
              size="sm"
              onClick={() => save.mutate()}
              loading={save.isPending}
              disabled={!draft.name.trim()}
            >
              <Save className="size-4" aria-hidden="true" />
              保存
            </Button>
          </div>
        </div>
      </header>

      {/* 三栏：字段导航 / 分组表单 / 实时预览 */}
      <div className="grid flex-1 grid-cols-1 xl:grid-cols-[220px_minmax(0,1fr)_380px]">
        <nav aria-label="字段分组" className="hidden border-r border-border px-3 py-4 xl:block">
          <div className="sticky top-20">
            <div className="px-2 pb-2 label-caps">字段分组</div>
            <NavList items={[...CARD_GROUPS]} activeId={activeGroup} onSelect={gotoGroup} />
            <p className="mt-4 px-2 text-xs leading-relaxed text-meta">
              分组只是导航，不改变模型看到的内容顺序 —— 真正决定顺序的是预设里的上下文组装规则。
            </p>
          </div>
        </nav>

        <ScrollArea className="min-w-0">
          <div ref={formRef} className="mx-auto max-w-2xl px-6 py-4">
            {mode === 'advanced' ? null : (
              <p className="mb-3 rounded-md border border-border bg-surface-warm px-3 py-2 text-sm leading-relaxed text-muted">
                快速模式只展开了最常用的字段。切到「完整」可以看到全部 —— 它们是折叠的，不是消失了。
              </p>
            )}
            <CardForm draft={draft} onChange={patch} mode={mode} />
          </div>
        </ScrollArea>

        <aside className="border-t border-border p-4 xl:border-l xl:border-t-0">
          <div className="sticky top-20">
            <CardPreview data={draft} />
          </div>
        </aside>
      </div>
    </div>
  );
}
