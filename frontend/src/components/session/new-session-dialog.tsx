import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { cardsApi, presetsApi, sessionsApi, worldbooksApi } from '@/api/client';
import { SAMPLE_CARDS, SAMPLE_PRESETS, SAMPLE_WORLDBOOKS } from '@/mocks/fixtures';
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
import { BookOpen, MessageSquare, UserRound, SlidersHorizontal, Info } from '@/components/icons';
import type { Session } from '@/api/types';

interface NewSessionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultCardId?: string;
  onCreated: (session: Session) => void;
}

/** 开会话：选卡 → 选预设 → 勾世界书 → 挑开场白（docs/03-uiux.md §7.3 空会话引导） */
export function NewSessionDialog({ open, onOpenChange, defaultCardId, onCreated }: NewSessionDialogProps) {
  const cardsQ = useQuery({ queryKey: ['cards', 'picker'], queryFn: () => cardsApi.list({ limit: 100 }), retry: false, enabled: open });
  const presetsQ = useQuery({ queryKey: ['presets', 'picker'], queryFn: () => presetsApi.list({ limit: 100 }), retry: false, enabled: open });
  const wbQ = useQuery({ queryKey: ['worldbooks', 'picker'], queryFn: () => worldbooksApi.list({ limit: 100 }), retry: false, enabled: open });

  const offline = cardsQ.isError;
  const cards = cardsQ.data?.items ?? (offline ? SAMPLE_CARDS : []);
  const presets = presetsQ.data?.items ?? (offline ? SAMPLE_PRESETS : []);
  const worldbooks = wbQ.data?.items ?? (offline ? SAMPLE_WORLDBOOKS : []);

  const [cardId, setCardId] = useState(defaultCardId ?? '');
  const [presetId, setPresetId] = useState('');
  const [wbIds, setWbIds] = useState<string[]>([]);
  const [greetingIndex, setGreetingIndex] = useState(-1);
  const [personaName, setPersonaName] = useState('你');
  const [withWorldbook, setWithWorldbook] = useState(true);

  // 打开时给出合理默认值（不让用户做无谓的选择题）
  useEffect(() => {
    if (!open) return;
    if (!cardId && cards.length > 0) setCardId(defaultCardId || cards[0].id);
    if (!presetId && presets.length > 0) setPresetId(presets[0].id);
    if (wbIds.length === 0 && worldbooks.length > 0) setWbIds([worldbooks[0].id]);
    setGreetingIndex(-1);
  }, [open, cards, presets, worldbooks, cardId, presetId, wbIds.length, defaultCardId]);

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
      sessionsApi.create({
        character_card_id: cardId,
        preset_id: presetId,
        worldbook_ids: withWorldbook ? wbIds : [],
        user_persona: { name: personaName || '你' },
        greeting_index: greetingIndex,
      }),
    onSuccess: (session) => {
      toast.success('会话已开始', '世界书与记忆会随对话自动生效。');
      onCreated(session);
    },
    onError: () => toast.danger('创建会话失败', '后端拒绝了这次请求，确认卡片与预设都还在。'),
  });

  const canCreate = Boolean(cardId && presetId) && !offline;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>开一场新会话</DialogTitle>
          <DialogDescription>
            选好角色卡就能开始 —— 预设与世界书已按常用档位预选，随时可以在会话里改。
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
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
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button variant="primary" onClick={() => create.mutate()} loading={create.isPending} disabled={!canCreate}>
            <MessageSquare className="size-4" aria-hidden="true" />
            开始会话
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
