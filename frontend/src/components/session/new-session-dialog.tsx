import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { cardsApi, presetsApi, sessionsApi, worldbooksApi, worldsApi } from '@/api/client';
import { SAMPLE_CARDS, SAMPLE_PRESETS, SAMPLE_WORLDBOOKS, SAMPLE_WORLDS } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Field } from '@/components/common/field';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { BookOpen, MessageSquare, UserRound, SlidersHorizontal, Info, Compass } from '@/components/icons';
import type { Session } from '@/api/types';

interface NewSessionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultCardId?: string;
  /** 打开时直接落到某个模式（如从「剧情」筛选空态进来的）。 */
  defaultMode?: SessionMode;
  onCreated: (session: Session) => void;
}

type SessionMode = 'rpg' | 'story';

/** 开会话：选卡 → 选预设 → 勾世界书 → 挑开场白（docs/03-uiux.md §7.3 空会话引导） */
export function NewSessionDialog({
  open,
  onOpenChange,
  defaultCardId,
  defaultMode = 'rpg',
  onCreated,
}: NewSessionDialogProps) {
  const cardsQ = useQuery({ queryKey: ['cards', 'picker'], queryFn: () => cardsApi.list({ limit: 100 }), retry: false, enabled: open });
  const presetsQ = useQuery({ queryKey: ['presets', 'picker'], queryFn: () => presetsApi.list({ limit: 100 }), retry: false, enabled: open });
  const wbQ = useQuery({ queryKey: ['worldbooks', 'picker'], queryFn: () => worldbooksApi.list({ limit: 100 }), retry: false, enabled: open });
  const worldsQ = useQuery({ queryKey: ['worlds', 'picker'], queryFn: () => worldsApi.list({ limit: 100 }), retry: false, enabled: open });

  const offline = cardsQ.isError;
  const cards = cardsQ.data?.items ?? (offline ? SAMPLE_CARDS : []);
  const presets = presetsQ.data?.items ?? (offline ? SAMPLE_PRESETS : []);
  const worldbooks = wbQ.data?.items ?? (offline ? SAMPLE_WORLDBOOKS : []);
  const worlds = worldsQ.data?.items ?? (worldsQ.isError ? SAMPLE_WORLDS : []);

  const [mode, setMode] = useState<SessionMode>(defaultMode);
  const [worldId, setWorldId] = useState('');
  const [cardId, setCardId] = useState(defaultCardId ?? '');
  const [presetId, setPresetId] = useState('');
  const [wbIds, setWbIds] = useState<string[]>([]);
  const [greetingIndex, setGreetingIndex] = useState(-1);
  const [personaName, setPersonaName] = useState('你');
  const [withWorldbook, setWithWorldbook] = useState(true);

  // 打开时给出合理默认值（不让用户做无谓的选择题）
  useEffect(() => {
    if (!open) return;
    setMode(defaultMode);
    if (!cardId && cards.length > 0) setCardId(defaultCardId || cards[0].id);
    if (!presetId && presets.length > 0) setPresetId(presets[0].id);
    if (wbIds.length === 0 && worldbooks.length > 0) setWbIds([worldbooks[0].id]);
    if (!worldId && worlds.length > 0) setWorldId(worlds[0].id);
    setGreetingIndex(-1);
  }, [open, cards, presets, worldbooks, worlds, cardId, presetId, wbIds.length, worldId, defaultCardId, defaultMode]);

  const isStory = mode === 'story';
  const selectedWorld = worlds.find((w) => w.id === worldId);

  /**
   * 世界观已建好且能对应到卡片时，自动选好「原点卡片」。
   *
   * 后端契约要求 `character_card_id` / `preset_id` **必填**（`SessionCreateRequest`
   * 两个字段都是 `UUID`），剧情分支里也会真的去查这两行、查不到就抛
   * `NotFoundError("角色卡不存在，无法开启剧情。")`。所以剧情模式不能只传 `world_id`。
   *
   * 既然必须选，就不该让用户白选一次 —— 优先级：
   *   1. cast 成员上显式写的 `card_id`（作者指定，最权威）
   *   2. cast 成员的 `name` 与卡片 `data.name` 同名（老数据的常见形态）
   *   3. 兜底：第一张卡（用户仍可在界面上改）
   */
  const linkedCardId = (() => {
    for (const member of selectedWorld?.cast ?? []) {
      if (member.card_id) {
        const hit = cards.find((c) => c.id === member.card_id);
        if (hit) return hit.id;
      }
    }
    for (const member of selectedWorld?.cast ?? []) {
      const hit = cards.find((c) => c.data.name === member.name);
      if (hit) return hit.id;
    }
    return '';
  })();

  // 切世界观时把「原点卡片」跟着带过去，除非作者已手改过
  const userTouchedCardRef = useRef(false);
  useEffect(() => {
    if (!open || !isStory) return;
    if (userTouchedCardRef.current) return;
    if (linkedCardId) setCardId(linkedCardId);
  }, [open, isStory, linkedCardId]);

  const selectedCard = cards.find((c) => c.id === cardId);
  const greetings = [
    { index: -1, label: '开场白', text: selectedCard?.data.first_mes ?? '' },
    ...(selectedCard?.data.alternate_greetings ?? []).map((g, i) => ({
      index: i,
      label: `备选开场白 ${i + 1}`,
      text: g,
    })),
  ];

  const create = useMutation({
    mutationFn: () =>
      sessionsApi.create(
        isStory
          ? {
              // 剧情模式：角色由世界观的 cast 定义。
              // 但后端 `SessionCreateRequest` 仍要求 card/preset 必填并会真的查询，
              // 所以这里必须传真实 id —— 空串会 422/400/404 三连失败。
              character_card_id: cardId,
              preset_id: presetId,
              world_id: worldId,
              user_persona: { name: personaName || '你' },
            }
          : {
              character_card_id: cardId,
              preset_id: presetId,
              worldbook_ids: withWorldbook ? wbIds : [],
              user_persona: { name: personaName || '你' },
              greeting_index: greetingIndex,
            },
      ),
    onSuccess: (session) => {
      toast.success(
        isStory ? '剧情已开演' : '会话已开始',
        isStory ? '导演会先铺开序幕，再安排在场角色依次开口。' : '世界书与记忆会随对话自动生效。',
      );
      onCreated(session);
    },
    onError: () =>
      toast.danger(
        isStory ? '创建剧情会话失败' : '创建会话失败',
        isStory
          ? '后端拒绝了这次请求。剧情模式仍需要一张「原点卡片」与一套预设入库，确认它们都还在。'
          : '后端拒绝了这次请求，确认卡片与预设都还在。',
      ),
  });

  // 两种模式都要求 card + preset：后端契约如此，前端不能靠空串绕过
  const canCreate = Boolean(worldId && cardId && presetId) && !offline;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isStory ? '开一场剧情' : '开一场新会话'}</DialogTitle>
          <DialogDescription>
            {isStory
              ? '挑一份世界观即可开局 —— 角色由它的角色群定义，导演负责安排谁在什么时候开口。'
              : '选好角色卡就能开始 —— 预设与世界书已按常用档位预选，随时可以在会话里改。'}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          {/* 模式选择：两种模式是同一种东西的两个形态，不做成两级导航 */}
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="会话模式">
            {(
              [
                { key: 'rpg', icon: MessageSquare, title: '单人对话', desc: '一张角色卡，一问一答' },
                { key: 'story', icon: Compass, title: '剧情世界', desc: '一份世界观，多角色同台' },
              ] as const
            ).map((m) => {
              const active = mode === m.key;
              const Icon = m.icon;
              return (
                <button
                  key={m.key}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setMode(m.key)}
                  className={
                    'flex items-start gap-2.5 rounded-md border px-3 py-2.5 text-left motion-fast ' +
                    (active
                      ? 'border-accent/40 bg-accent-subtle'
                      : 'border-border bg-surface-warm hover:bg-surface')
                  }
                >
                  <Icon
                    className={active ? 'mt-0.5 size-4 shrink-0 text-accent' : 'mt-0.5 size-4 shrink-0 text-muted'}
                    aria-hidden="true"
                  />
                  <span className="min-w-0">
                    <span className={'block text-sm font-medium ' + (active ? 'text-accent' : 'text-fg')}>
                      {m.title}
                    </span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-muted">{m.desc}</span>
                  </span>
                </button>
              );
            })}
          </div>

          {isStory ? (
            <>
              {worlds.length === 0 ? (
                <p className="rounded-md border border-border bg-warn-subtle px-3 py-2 text-sm leading-relaxed text-fg-2">
                  还没有世界观。先去
                  <Link to="/worlds/new" className="mx-1 text-accent underline underline-offset-2">
                    新建一份世界观
                  </Link>
                  ，把角色群和大纲写好，才能开剧情。
                </p>
              ) : null}

              <Field label="世界观" htmlFor="ns-world" hint="决定这场戏发生在哪、有哪些角色。">
                <Select value={worldId} onValueChange={setWorldId}>
                  <SelectTrigger id="ns-world">
                    <SelectValue placeholder="选一份世界观" />
                  </SelectTrigger>
                  <SelectContent>
                    {worlds.map((w) => (
                      <SelectItem key={w.id} value={w.id}>
                        <span className="inline-flex items-center gap-2">
                          <Compass className="size-3.5" aria-hidden="true" />
                          {w.title || '未命名世界'}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              {selectedWorld ? (
                <div className="space-y-2 rounded-md border border-border bg-reading-surface px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-fg">{selectedWorld.title}</span>
                    <Badge variant="accent">{selectedWorld.cast.length} 名角色</Badge>
                    {selectedWorld.outline?.nodes?.length ? (
                      <Badge variant="outline">{selectedWorld.outline.nodes.length} 个节点</Badge>
                    ) : null}
                  </div>
                  {selectedWorld.setting?.summary ? (
                    <p className="max-h-24 overflow-y-auto text-xs leading-relaxed text-fg-2">
                      {selectedWorld.setting.summary}
                    </p>
                  ) : null}
                  {selectedWorld.cast.length > 0 ? (
                    <p className="text-xs text-muted">
                      在场：
                      {selectedWorld.cast
                        .slice(0, 6)
                        .map((c) => c.name)
                        .join('、')}
                      {selectedWorld.cast.length > 6 ? ` 等 ${selectedWorld.cast.length} 人` : ''}
                    </p>
                  ) : (
                    <p className="flex items-start gap-2 text-xs leading-relaxed text-warn">
                      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                      这份世界观还没有角色群，导演将无人可用。建议先回去补上 cast。
                    </p>
                  )}
                </div>
              ) : null}

              <Field
                label="原点卡片"
                htmlFor="ns-story-card"
                hint="剧情里由世界观的角色群说话，这张卡只作锚点（已尽量按世界观的关联卡自动选好）。"
              >
                <Select
                  value={cardId}
                  onValueChange={(v) => {
                    userTouchedCardRef.current = true;
                    setCardId(v);
                  }}
                >
                  <SelectTrigger id="ns-story-card">
                    <SelectValue placeholder="选一张角色卡" />
                  </SelectTrigger>
                  <SelectContent>
                    {cards.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        <span className="inline-flex items-center gap-2">
                          <UserRound className="size-3.5" aria-hidden="true" />
                          {c.data.name}
                          {c.id === linkedCardId ? '（世界观关联）' : ''}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="预设" htmlFor="ns-story-preset" hint="决定模型的说话方式。">
                  <Select value={presetId} onValueChange={setPresetId}>
                    <SelectTrigger id="ns-story-preset">
                      <SelectValue placeholder="选一套预设" />
                    </SelectTrigger>
                    <SelectContent>
                      {presets.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          <span className="inline-flex items-center gap-2">
                            <SlidersHorizontal className="size-3.5" aria-hidden="true" />
                            {p.data.name}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>

                <Field label="我以谁的身份入场" htmlFor="ns-persona-story" hint="会替换 {{user}}，导演据此称呼你。">
                  <Input
                    id="ns-persona-story"
                    value={personaName}
                    onChange={(e) => setPersonaName(e.target.value)}
                    placeholder="你"
                  />
                </Field>
              </div>
            </>
          ) : (
            <>
              {cards.length === 0 ? (
                <p className="rounded-md border border-border bg-warn-subtle px-3 py-2 text-sm leading-relaxed text-fg-2">
                  内容库里还没有角色卡。先
                  <Link to="/setup" className="mx-1 text-accent underline underline-offset-2">
                    安装示例内容
                  </Link>
                  或导入一张卡。
                </p>
              ) : null}

              <Field label="角色卡" htmlFor="ns-card" hint="决定这次扮演谁。">
                <Select value={cardId} onValueChange={(v) => { setCardId(v); setGreetingIndex(-1); }}>
                  <SelectTrigger id="ns-card">
                    <SelectValue placeholder="选一张角色卡" />
                  </SelectTrigger>
                  <SelectContent>
                    {cards.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        <span className="inline-flex items-center gap-2">
                          <UserRound className="size-3.5" aria-hidden="true" />
                          {c.data.name}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="预设" htmlFor="ns-preset" hint="决定模型的说话方式。">
                  <Select value={presetId} onValueChange={setPresetId}>
                    <SelectTrigger id="ns-preset">
                      <SelectValue placeholder="选一套预设" />
                    </SelectTrigger>
                    <SelectContent>
                      {presets.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          <span className="inline-flex items-center gap-2">
                            <SlidersHorizontal className="size-3.5" aria-hidden="true" />
                            {p.data.name}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>

                <Field label="我以谁的身份对话" htmlFor="ns-persona" hint="会替换 {{user}}。">
                  <Input
                    id="ns-persona"
                    value={personaName}
                    onChange={(e) => setPersonaName(e.target.value)}
                    placeholder="你"
                  />
                </Field>
              </div>

              <Field label="开场白" htmlFor="ns-greeting" hint="想换个开局就挑一条备选。">
                <Select value={String(greetingIndex)} onValueChange={(v) => setGreetingIndex(Number(v))}>
                  <SelectTrigger id="ns-greeting">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {greetings.map((g) => (
                      <SelectItem key={g.index} value={String(g.index)}>
                        {g.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              {greetings.find((g) => g.index === greetingIndex)?.text ? (
                <p className="max-h-28 overflow-y-auto rounded-md border border-border bg-reading-surface px-3 py-2 text-sm leading-reading text-fg-2">
                  {greetings.find((g) => g.index === greetingIndex)?.text}
                </p>
              ) : (
                <p className="flex items-start gap-2 rounded-md border border-border bg-surface-warm px-3 py-2 text-sm leading-relaxed text-muted">
                  <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden="true" />
                  这张卡还没写开场白。会话开始后角色不会主动说话，你可以先发第一句。
                </p>
              )}

              {worldbooks.length > 0 ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-warm px-3 py-2.5">
                    <div className="flex items-start gap-2">
                      <BookOpen className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden="true" />
                      <div>
                        <div className="text-base text-fg">挂上世界书</div>
                        <p className="mt-0.5 text-xs leading-relaxed text-muted">
                          一张卡可以同时绑多本。命中时可观测，不怕"为什么没触发"。
                        </p>
                      </div>
                    </div>
                    <Switch checked={withWorldbook} onCheckedChange={setWithWorldbook} label="挂上世界书" />
                  </div>

                  {withWorldbook ? (
                    <ul className="space-y-1">
                      {worldbooks.map((wb) => {
                        const checked = wbIds.includes(wb.id);
                        return (
                          <li key={wb.id}>
                            <label className="flex cursor-pointer items-center gap-2.5 rounded-sm border border-border px-2.5 py-2 motion-fast hover:bg-surface-warm">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() =>
                                  setWbIds(checked ? wbIds.filter((x) => x !== wb.id) : [...wbIds, wb.id])
                                }
                                className="size-3.5 accent-[var(--color-accent)]"
                              />
                              <span className="min-w-0 flex-1 truncate text-sm text-fg-2">
                                {wb.data.name || '未命名世界书'}
                              </span>
                              <span className="tech-meta shrink-0">{wb.data.entries.length} 条</span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button variant="primary" onClick={() => create.mutate()} loading={create.isPending} disabled={!canCreate}>
            {isStory ? <Compass className="size-4" aria-hidden="true" /> : <MessageSquare className="size-4" aria-hidden="true" />}
            {isStory ? '开始剧情' : '开始会话'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
