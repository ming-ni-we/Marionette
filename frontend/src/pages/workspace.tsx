import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient, useQueries } from '@tanstack/react-query';
import { cn, relativeTime } from '@/lib/utils';
import { cardsApi, ioApi, presetsApi, sessionsApi, worldbooksApi } from '@/api/client';
import type { Card, Preset, Session, WorldBook } from '@/api/types';
import { SAMPLE_CARDS, SAMPLE_PRESETS, SAMPLE_SESSIONS, SAMPLE_WORLDBOOKS } from '@/mocks/fixtures';
import { toast, useUiStore } from '@/stores/ui';
import { PageHeader } from '@/components/common/page-header';
import { LibraryToolbar, ActiveTagChips } from '@/components/common/library-toolbar';
import { EmptyState } from '@/components/common/empty-state';
import { OfflineBanner } from '@/components/common/offline-banner';
import { QuickStartPanel } from '@/components/workspace/quick-start-panel';
import { ContinueStrip, type ContinueItem } from '@/components/workspace/continue-strip';
import {
  CardSection,
  PresetSection,
  SessionSection,
  WorldBookSection,
} from '@/components/workspace/library-sections';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { UserRound, CirclePlus, Upload, Pencil, PanelLeftClose, PanelLeftOpen } from '@/components/icons';
import { useLibraryController, aggregateTags } from '@/hooks/use-library';
import { demoFilter, filterDemoSessions } from '@/lib/demo-filter';

export function WorkspacePage() {
  const qc = useQueryClient();
  const lib = useLibraryController();
  const quickStartOpen = useUiStore((s) => s.quickStartOpen);
  const setQuickStartOpen = useUiStore((s) => s.setQuickStartOpen);
  const [importing, setImporting] = useState(false);

  const [cards, worldbooks, presets, sessions] = useQueries({
    queries: [
      { queryKey: ['cards', lib.searchQuery], queryFn: () => cardsApi.list(lib.searchQuery), retry: false },
      { queryKey: ['worldbooks', lib.searchQuery], queryFn: () => worldbooksApi.list(lib.searchQuery), retry: false },
      { queryKey: ['presets', lib.searchQuery], queryFn: () => presetsApi.list(lib.searchQuery), retry: false },
      { queryKey: ['sessions', lib.searchQuery], queryFn: () => sessionsApi.list(lib.searchQuery), retry: false },
    ],
  });

  // 后端不可达 → 切到本地演示数据（并在页面顶部明确标注）
  const offline = cards.isError;

  const cardItems: Card[] = offline
    ? demoFilter(SAMPLE_CARDS, lib.debouncedQuery, lib.tags)
    : cards.data?.items ?? [];
  const wbItems: WorldBook[] = offline
    ? demoFilter(SAMPLE_WORLDBOOKS, lib.debouncedQuery, lib.tags)
    : worldbooks.data?.items ?? [];
  const presetItems: Preset[] = offline
    ? demoFilter(SAMPLE_PRESETS, lib.debouncedQuery, lib.tags)
    : presets.data?.items ?? [];
  const sessionItems: Session[] = offline
    ? filterDemoSessions(SAMPLE_SESSIONS, lib.debouncedQuery)
    : sessions.data?.items ?? [];

  const availableTags = useMemo(
    () =>
      aggregateTags([
        ...cardItems.map((c) => ({ tags: c.data.tags })),
        ...wbItems.map((w) => ({ tags: w.data.extensions?.tags as string[] | undefined })),
        ...presetItems.map((p) => ({ tags: p.data.extensions?.tags as string[] | undefined })),
      ]),
    [cardItems, wbItems, presetItems],
  );

  const removeCard = useMutation({
    mutationFn: (id: string) => cardsApi.remove(id),
    onSuccess: () => {
      toast.success('已删除角色卡');
      void qc.invalidateQueries({ queryKey: ['cards'] });
    },
    onError: () => toast.danger('删除失败', '后端没有确认这次删除。'),
  });

  const importCard = useMutation({
    mutationFn: (file: File) => ioApi.importCard(file),
    onSuccess: (res) => {
      toast.success(
        '导入完成',
        `识别为 ${res.source_format.toUpperCase()} 格式${res.warnings.length ? `，有 ${res.warnings.length} 条提示` : ''}。`,
      );
      void qc.invalidateQueries({ queryKey: ['cards'] });
    },
    onError: () => toast.danger('导入失败', '确认文件是 SillyTavern 的 .json / .png 角色卡。'),
    onSettled: () => setImporting(false),
  });

  const continueItems: ContinueItem[] = useMemo(() => {
    const fromSessions: ContinueItem[] = sessionItems.slice(0, 3).map((s) => ({
      id: s.id,
      kind: 'session',
      title: s.scene.summary || '未命名会话',
      subtitle: `${s.state_machine.turn} 轮 · ${relativeTime(s.updated_at)}`,
      to: `/sessions/${s.id}`,
    }));
    const fromCards: ContinueItem[] = cardItems.slice(0, 2).map((c) => ({
      id: c.id,
      kind: 'card',
      title: c.data.name,
      subtitle: `最近修改 · ${relativeTime(c.updated_at)}`,
      to: `/cards/${c.id}`,
    }));
    return [...fromSessions, ...fromCards];
  }, [sessionItems, cardItems]);

  const totalCount = cardItems.length + wbItems.length + presetItems.length;
  const libraryEmpty = !offline && totalCount === 0 && sessionItems.length === 0 && !lib.isFiltering;
  const filteredEmpty = lib.isFiltering && totalCount === 0 && sessionItems.length === 0;

  return (
    <div className="flex min-h-dvh">
      <div className="min-w-0 flex-1">
        <PageHeader
          title="内容库"
          description="角色卡、世界书、预设都在这里。搜索用中文子串就能命中，不需要精确分词。"
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link to="/cards/new">
                  <CirclePlus className="size-4" aria-hidden="true" />
                  新建角色卡
                </Link>
              </Button>
              <label className="inline-flex">
                <input
                  type="file"
                  accept=".json,.png,.webp,application/json,image/png,image/webp"
                  className="sr-only"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setImporting(true);
                      importCard.mutate(file);
                    }
                    e.target.value = '';
                  }}
                />
                <span
                  className={cn(
                    'inline-flex h-[var(--density-control-height)] cursor-pointer items-center gap-2 rounded-sm border border-border px-3 text-base text-fg-2 motion-fast hover:border-border-strong hover:bg-surface-warm',
                    importing && 'pointer-events-none opacity-60',
                  )}
                >
                  <Upload className="size-4" aria-hidden="true" />
                  {importing ? '导入中…' : '导入酒馆卡'}
                </span>
              </label>
            </>
          }
          meta={
            <span className="flex items-center gap-2">
              <Badge variant="outline">studio · 高密度</Badge>
              <span className="tech-meta">
                {cardItems.length} 角色卡 · {wbItems.length} 世界书 · {presetItems.length} 预设 ·{' '}
                {sessionItems.length} 会话
              </span>
            </span>
          }
        />

        {offline ? (
          <OfflineBanner>
            下面是内置演示数据，你可以直接浏览交互。要开始真实使用，去
            <Link to="/setup" className="mx-1 text-accent underline underline-offset-2">
              首启向导
            </Link>
            接入模型后端。
          </OfflineBanner>
        ) : null}

        <div className="space-y-5 px-6 py-5">
          <LibraryToolbar
            query={lib.query}
            onQueryChange={lib.setQuery}
            selectedTags={lib.tags}
            onSelectedTagsChange={lib.setTags}
            availableTags={availableTags}
            sort={lib.sort}
            onSortChange={lib.setSort}
            order={lib.order}
            onOrderChange={lib.setOrder}
            resultCount={
              offline ? cardItems.length + wbItems.length + presetItems.length + sessionItems.length : undefined
            }
          />
          <ActiveTagChips tags={lib.tags} onRemove={(t) => lib.setTags(lib.tags.filter((x) => x !== t))} />

          {libraryEmpty ? (
            <EmptyState
              icon={UserRound}
              title="还没有角色卡"
              description="导入一张 Tavern 卡，或从内置「现代日常向」示例开始 —— 装完之后可以直接开一场会话，不用先自己写设定。"
              actions={
                <>
                  <Button variant="primary" asChild>
                    <Link to="/setup">
                      <CirclePlus className="size-4" aria-hidden="true" />
                      安装内置示例内容
                    </Link>
                  </Button>
                  <Button variant="secondary" asChild>
                    <Link to="/cards/new">
                      <Pencil className="size-4" aria-hidden="true" />
                      从零创建
                    </Link>
                  </Button>
                </>
              }
              hint="也可以把 .json / .png 角色卡直接拖到这里导入。"
            />
          ) : filteredEmpty ? (
            <EmptyState
              icon={UserRound}
              title="没有匹配的结果"
              description={`当前筛选条件下没有任何内容。关键词「${lib.debouncedQuery}」${lib.tags.length ? `，标签 ${lib.tags.join('、')}` : ''}。`}
              actions={
                <Button variant="secondary" onClick={lib.reset}>
                  清除全部筛选
                </Button>
              }
            />
          ) : (
            <>
              {continueItems.length > 0 ? <ContinueStrip items={continueItems} /> : null}
              <CardSection
                items={cardItems}
                query={lib.debouncedQuery}
                offline={offline}
                onRemove={(id) => removeCard.mutate(id)}
              />
              <Separator />
              <WorldBookSection items={wbItems} query={lib.debouncedQuery} />
              <Separator />
              <PresetSection items={presetItems} query={lib.debouncedQuery} />
              <Separator />
              <SessionSection items={sessionItems} />
            </>
          )}
        </div>
      </div>

      {/* 右侧快速开始（可收起） */}
      <aside
        className={cn(
          'hidden shrink-0 border-l border-border bg-surface-sunken transition-[width] duration-[var(--dur-moderate)] xl:block',
          quickStartOpen ? 'w-[300px]' : 'w-12',
        )}
      >
        <div className="sticky top-0 flex h-dvh flex-col p-3">
          <button
            type="button"
            onClick={() => setQuickStartOpen(!quickStartOpen)}
            aria-label={quickStartOpen ? '收起快速开始面板' : '展开快速开始面板'}
            aria-expanded={quickStartOpen}
            className={cn(
              'mb-2 inline-flex items-center gap-1.5 rounded-sm px-2 py-1.5 text-sm text-muted motion-fast hover:bg-surface-warm hover:text-fg',
              !quickStartOpen && 'justify-center',
            )}
          >
            {quickStartOpen ? (
              <PanelLeftClose className="size-4" aria-hidden="true" />
            ) : (
              <PanelLeftOpen className="size-4" aria-hidden="true" />
            )}
            {quickStartOpen ? '收起' : null}
          </button>
          {quickStartOpen ? (
            <>
              <QuickStartPanel />
              <div className="mt-auto flex items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 py-2">
                <span className="text-xs text-muted">下次自动展开</span>
                <Switch
                  checked={quickStartOpen}
                  onCheckedChange={setQuickStartOpen}
                  label="下次自动展开快速开始面板"
                />
              </div>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
