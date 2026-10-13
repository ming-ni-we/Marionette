import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { emptyWorldBookData, worldbooksApi } from '@/api/client';
import type { WorldBookData, WorldBookEntry, WorldBookTestResult } from '@/api/types';
import { mockWorldBookTest, SAMPLE_WORLDBOOKS } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';
import { WorldBookHeader } from '@/components/worldbook/editor-header';
import { EntryList } from '@/components/worldbook/entry-list';
import { EntryEditor } from '@/components/worldbook/entry-editor';
import { WorldBookSettings } from '@/components/worldbook/worldbook-settings';
import { newEntry as makeEntry } from '@/components/worldbook/entry-defaults';
import { HitTestPanel } from '@/components/worldbook/hit-test-panel';
import { ErrorState, EmptyState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CirclePlus, Copy, Trash2, KeyRound, Settings as SettingsIcon } from '@/components/icons';

export function WorldBookEditorPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  // 路由 /worldbooks/new 命中静态段后 useParams() 为空 → id=''，同样视为新建
  const isNew = !id || id === 'new';

  const query = useQuery({
    queryKey: ['worldbook', id],
    queryFn: () => worldbooksApi.get(id),
    enabled: !isNew,
    retry: false,
  });

  const demoBook = !isNew ? SAMPLE_WORLDBOOKS.find((w) => w.id === id) : undefined;
  const offline = query.isError;

  const [draft, setDraft] = useState<WorldBookData>(emptyWorldBookData);
  const [dirty, setDirty] = useState(false);
  const [selected, setSelected] = useState(0);
  const [tab, setTab] = useState<'entry' | 'settings'>('entry');
  const [result, setResult] = useState<WorldBookTestResult | null>(null);
  const loadedRef = useRef<string | null>(null);

  useEffect(() => {
    const source = query.data?.data ?? (offline ? demoBook?.data : undefined);
    const key = query.data?.id ?? (offline && demoBook ? demoBook.id : null);
    if (source && key && loadedRef.current !== key) {
      setDraft(source);
      setSelected(0);
      setDirty(false);
      loadedRef.current = key;
    }
  }, [query.data, offline, demoBook]);

  useEffect(() => {
    if (isNew) {
      setDraft(emptyWorldBookData());
      setDirty(false);
      loadedRef.current = 'new';
    }
  }, [isNew]);

  const entries = draft.entries;
  const current = entries[selected];

  const patchBook = (p: Partial<WorldBookData>) => {
    setDraft((d) => ({ ...d, ...p }));
    setDirty(true);
  };
  const patchEntry = (p: Partial<WorldBookEntry>) => {
    setDraft((d) => ({
      ...d,
      entries: d.entries.map((e, i) => (i === selected ? { ...e, ...p } : e)),
    }));
    setDirty(true);
  };
  const addEntry = () => {
    setDraft((d) => ({ ...d, entries: [...d.entries, makeEntry()] }));
    setSelected(entries.length);
    setTab('entry');
    setDirty(true);
  };
  const toggleEntry = (i: number, enabled: boolean) => {
    setDraft((d) => ({ ...d, entries: d.entries.map((e, k) => (k === i ? { ...e, enabled } : e)) }));
    setDirty(true);
  };
  const duplicateEntry = () => {
    setDraft((d) => {
      const next = [...d.entries];
      next.splice(selected + 1, 0, { ...next[selected] });
      return { ...d, entries: next };
    });
    setSelected(selected + 1);
    setDirty(true);
  };
  const removeEntry = () => {
    setDraft((d) => ({ ...d, entries: d.entries.filter((_, k) => k !== selected) }));
    setSelected(Math.max(0, selected - 1));
    setDirty(true);
  };

  const hitCount = useMemo(() => entries.filter((e) => e.enabled).length, [entries]);

  const save = useMutation({
    mutationFn: () => {
      const payload = { spec: 'rpg_worldbook' as const, spec_version: '1.0', data: draft };
      return isNew ? worldbooksApi.create(payload) : worldbooksApi.update(id, payload);
    },
    onSuccess: (wb) => {
      setDirty(false);
      toast.success(isNew ? '世界书已创建' : '已保存');
      void qc.invalidateQueries({ queryKey: ['worldbooks'] });
      if (isNew) navigate(`/worldbooks/${wb.id}`, { replace: true });
    },
    onError: () => toast.danger('保存失败', '后端拒绝了这次写入。'),
  });

  const runTest = useMutation({
    mutationFn: async (text: string) => {
      if (offline) return mockWorldBookTest(draft, text, draft.scan_depth);
      return worldbooksApi.test(id, { sample_text: text, scan_depth: draft.scan_depth });
    },
    onSuccess: (res) => setResult(res),
    onError: () => toast.danger('命中测试失败', '后端没有返回判定结果。'),
  });

  if (!isNew && query.isError && !demoBook) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-10">
        <ErrorState
          description={`没找到这本文档（id: ${id}）。它可能已被删除，或当前后端实例换了数据库。`}
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link to="/">回到内容库</Link>
              </Button>
              <Button variant="ghost" asChild>
                <Link to="/worldbooks/new">新建一本世界书</Link>
              </Button>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <WorldBookHeader
        name={draft.name}
        isNew={isNew}
        demo={offline && Boolean(demoBook)}
        dirty={dirty}
        entriesLength={entries.length}
        enabledCount={hitCount}
        budget={draft.token_budget}
        saving={save.isPending}
        onSave={() => save.mutate()}
      />

      <div className="grid flex-1 grid-cols-1 xl:grid-cols-[300px_minmax(0,1fr)_400px]">
        <EntryList
          entries={entries}
          selected={selected}
          onSelect={(i) => {
            setSelected(i);
            setTab('entry');
          }}
          onToggle={toggleEntry}
          onAdd={addEntry}
        />

        {/* 中：条目编辑 / 世界书设置 */}
        <ScrollArea className="min-w-0">
          <div className="mx-auto max-w-2xl px-6 py-4">
            <Tabs value={tab} onValueChange={(v) => setTab(v as 'entry' | 'settings')}>
              <TabsList>
                <TabsTrigger value="entry">
                  <KeyRound aria-hidden="true" />
                  条目{current ? ` ${selected + 1}` : ''}
                </TabsTrigger>
                <TabsTrigger value="settings">
                  <SettingsIcon aria-hidden="true" />
                  世界书设置
                </TabsTrigger>
              </TabsList>

              <TabsContent value="entry" className="mt-4">
                {current ? (
                  <>
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <span className="tech-meta">
                        {current.enabled ? '已启用' : '已停用'} · 第 {selected + 1} / {entries.length} 条
                      </span>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" onClick={duplicateEntry}>
                          <Copy className="size-4" aria-hidden="true" />
                          复制一条
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-danger"
                          onClick={removeEntry}
                        >
                          <Trash2 className="size-4" aria-hidden="true" />
                          删除
                        </Button>
                      </div>
                    </div>
                    <EntryEditor entry={current} onChange={patchEntry} />
                  </>
                ) : (
                  <EmptyState
                    icon={KeyRound}
                    title="先选一条条目"
                    description="左侧列表里还没有可编辑的条目。点左上角的加号，或下面的按钮开始。"
                    actions={
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setDraft((d) => ({ ...d, entries: [makeEntry()] }));
                          setSelected(0);
                          setDirty(true);
                        }}
                      >
                        <CirclePlus className="size-4" aria-hidden="true" />
                        添加第一条条目
                      </Button>
                    }
                  />
                )}
              </TabsContent>

              <TabsContent value="settings" className="mt-4">
                <WorldBookSettings data={draft} onChange={patchBook} />
              </TabsContent>
            </Tabs>
          </div>
        </ScrollArea>

        {/* 右：命中测试（差异化视觉点） */}
        <aside className="border-t border-border p-4 xl:border-l xl:border-t-0">
          <div className="sticky top-20">
            {dirty ? (
              <p className="mb-2 text-xs leading-relaxed text-warn">
                有未保存的修改。命中测试跑的是<strong className="font-medium">已保存</strong>
                的版本，先保存再测更准。
              </p>
            ) : null}
            <HitTestPanel
              entryCount={entries.length}
              result={result}
              loading={runTest.isPending}
              onRun={(text) => runTest.mutate(text)}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
