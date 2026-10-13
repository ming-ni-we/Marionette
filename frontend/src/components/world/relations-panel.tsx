import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { EmptyState } from '@/components/common/empty-state';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Trash2, CirclePlus, Network } from '@/components/icons';
import type { WorldCastMember, WorldRelation } from '@/api/types';

/** 关系类型预设（kind 是自由文本，这里只是常用值）。 */
const KIND_PRESETS = ['旧识', '上下级', '宿敌', '血亲', '陌生人', '合伙人'];

/**
 * tension → 文字。裸数字没有意义，必须给出可读语义，
 * 否则用户不知道 -0.3 和 -0.6 有什么区别。
 */
export function tensionLabel(tension: number): { text: string; tone: string } {
  if (tension <= -0.6) return { text: '敌意', tone: 'text-danger' };
  if (tension <= -0.2) return { text: '戒备', tone: 'text-warn' };
  if (tension < 0.2) return { text: '中立', tone: 'text-meta' };
  if (tension < 0.6) return { text: '亲近', tone: 'text-fg-2' };
  return { text: '亲密', tone: 'text-success' };
}

/** 删除角色时清理引用它的关系边（否则会留下指向不存在角色的死边）。 */
export function pruneRelations(
  relations: WorldRelation[],
  cast: WorldCastMember[],
): WorldRelation[] {
  const alive = new Set(cast.map((c) => c.id));
  return relations.filter((r) => alive.has(r.from) && alive.has(r.to));
}

/**
 * 关系图编辑器。
 *
 * 关系边是导演判断「这两个人该怎么互相说话」的主要依据，也会被渲染进
 * `context_assembler` 的 relations 段（按 tension 绝对值降序，超预算时先丢最弱边）。
 * 因此这里刻意只允许**从角色群里选人**，不允许自由输入 id——防止写出悬空边。
 */
export function WorldRelationsPanel({
  relations,
  cast,
  onChange,
}: {
  relations: WorldRelation[];
  cast: WorldCastMember[];
  onChange: (next: WorldRelation[]) => void;
}) {
  const castOptions = useMemo(
    () => cast.filter((c) => c.id).map((c) => ({ id: c.id, name: c.name || c.id })),
    [cast],
  );

  const setAt = (i: number, patch: Partial<WorldRelation>) =>
    onChange(relations.map((r, k) => (k === i ? { ...r, ...patch } : r)));

  const add = () => {
    const from = castOptions[0]?.id ?? '';
    const to = castOptions.find((c) => c.id !== from)?.id ?? from;
    onChange([...relations, { from, to, kind: '', tension: 0, note: '' }]);
  };

  const disabled = castOptions.length < 2;

  return (
    <GroupSection
      id="world-relations"
      title="角色关系"
      description="两个人之间「怎么想对方」。这是导演安排谁先开口、谁该沉默的主要依据。"
      summary={relations.length > 0 ? `${relations.length} 条` : undefined}
      defaultOpen
    >
      {disabled ? (
        <EmptyState
          size="compact"
          icon={Network}
          title="至少要有两个角色"
          description={
            castOptions.length === 0
              ? '先去上面的「角色群」加人。关系图的两端都必须是已存在的角色。'
              : '关系至少需要两端。再加一个角色，就能定义他们之间的关系了。'
          }
        />
      ) : relations.length === 0 ? (
        <EmptyState
          size="compact"
          icon={Network}
          title="还没有定义关系"
          description="不写也能跑——导演会默认他们互不相识。但写上一两条，故事张力会明显不一样。"
          actions={
            <Button variant="secondary" onClick={add}>
              <CirclePlus className="size-4" aria-hidden="true" />
              添加第一条关系
            </Button>
          }
        />
      ) : (
        <ul className="space-y-3">
          {relations.map((rel, i) => {
            const tension = typeof rel.tension === 'number' ? rel.tension : 0;
            const { text, tone } = tensionLabel(tension);
            // 死边（引用已删除角色）只可能出现在「先建关系后删角色」的中间态，
            // 这里显式提示而非静默丢弃，让用户知道该修哪条。
            const dangling =
              !castOptions.some((c) => c.id === rel.from) ||
              !castOptions.some((c) => c.id === rel.to);
            return (
              <li
                key={`rel-${i}`}
                className={cn(
                  'rounded-md border p-3',
                  dangling ? 'border-warn bg-surface-warm' : 'border-border bg-surface',
                )}
              >
                <div className="grid items-end gap-3 sm:grid-cols-[1fr_auto_1fr]">
                  <Field label="谁" htmlFor={`rel-from-${i}`}>
                    <Select value={rel.from} onValueChange={(v) => setAt(i, { from: v })}>
                      <SelectTrigger id={`rel-from-${i}`}>
                        <SelectValue placeholder="选择角色" />
                      </SelectTrigger>
                      <SelectContent>
                        {castOptions.map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>

                  <span className="hidden pb-1.5 text-meta sm:block" aria-hidden="true">
                    →
                  </span>

                  <Field label="对谁" htmlFor={`rel-to-${i}`}>
                    <Select value={rel.to} onValueChange={(v) => setAt(i, { to: v })}>
                      <SelectTrigger id={`rel-to-${i}`}>
                        <SelectValue placeholder="选择角色" />
                      </SelectTrigger>
                      <SelectContent>
                        {castOptions.map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>

                {dangling ? (
                  <p className="mt-2 text-xs leading-relaxed text-warn">
                    这条关系指向的角色已不在角色群里，保存前请修正或删除它。
                  </p>
                ) : null}

                <div className="mt-3 grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)]">
                  <Field label="关系" htmlFor={`rel-kind-${i}`} optional>
                    <Input
                      id={`rel-kind-${i}`}
                      list={`rel-kind-presets-${i}`}
                      value={rel.kind ?? ''}
                      onChange={(e) => setAt(i, { kind: e.target.value })}
                      placeholder="旧识 / 宿敌…"
                    />
                    <datalist id={`rel-kind-presets-${i}`}>
                      {KIND_PRESETS.map((k) => (
                        <option key={k} value={k} />
                      ))}
                    </datalist>
                  </Field>

                  <Field label="张力度" htmlFor={`rel-tension-${i}`}>
                    <div className="flex items-center gap-3">
                      <input
                        id={`rel-tension-${i}`}
                        type="range"
                        min={-1}
                        max={1}
                        step={0.1}
                        value={tension}
                        onChange={(e) => setAt(i, { tension: Number(e.target.value) })}
                        className="h-1.5 flex-1 cursor-pointer accent-[var(--color-accent)]"
                        aria-valuetext={`${tension.toFixed(1)} ${text}`}
                      />
                      <Badge variant="neutral" className={cn('shrink-0 font-mono', tone)}>
                        {tension.toFixed(1)} · {text}
                      </Badge>
                    </div>
                  </Field>
                </div>

                <div className="mt-3 flex items-start gap-2">
                  <Input
                    value={rel.note ?? ''}
                    aria-label={`关系 ${i + 1} 的补充说明`}
                    onChange={(e) => setAt(i, { note: e.target.value })}
                    placeholder="补充说明（可选）：例如「三年前欠他一条命」"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="shrink-0 text-danger"
                    aria-label={`删除第 ${i + 1} 条关系`}
                    onClick={() => onChange(relations.filter((_, k) => k !== i))}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {!disabled && relations.length > 0 ? (
        <Button type="button" variant="secondary" size="sm" onClick={add}>
          <CirclePlus className="size-4" aria-hidden="true" />
          添加关系
        </Button>
      ) : null}
    </GroupSection>
  );
}
