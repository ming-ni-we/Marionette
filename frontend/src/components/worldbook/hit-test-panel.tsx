import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { EmptyState } from '@/components/common/empty-state';
import {
  CircleCheck,
  CircleX,
  TriangleAlert,
  KeyRound,
  Coins,
  Filter,
  Sparkles,
} from '@/components/icons';
import type { WorldBookMatchType, WorldBookTestEntry, WorldBookTestResult } from '@/api/types';

type EntryState = 'miss' | 'hit_in_budget' | 'hit_evicted';

/** 三态判定：这是本产品最关键的差异化可视化——竞品对"为什么没触发"完全不可见 */
export function entryState(entry: WorldBookTestEntry): EntryState {
  if (!entry.matched) return 'miss';
  return entry.in_budget ? 'hit_in_budget' : 'hit_evicted';
}

const STATE_META: Record<
  EntryState,
  { label: string; Icon: typeof CircleCheck; tone: string; row: string; badge: 'success' | 'warn' | 'outline' }
> = {
  hit_in_budget: {
    label: '命中 · 已注入',
    Icon: CircleCheck,
    tone: 'text-success',
    row: 'border-border bg-success-subtle',
    badge: 'success',
  },
  hit_evicted: {
    label: '命中 · 被预算挤出',
    Icon: TriangleAlert,
    tone: 'text-warn',
    row: 'border-border bg-warn-subtle',
    badge: 'warn',
  },
  miss: {
    label: '未命中',
    Icon: CircleX,
    tone: 'text-meta',
    row: 'border-border bg-transparent',
    badge: 'outline',
  },
};

const MATCH_TYPE_LABEL: Record<WorldBookMatchType, string> = {
  constant: '常驻',
  keyword: '关键词',
  regex: '正则',
  vector: '向量',
  none: '—',
};

const POSITION_LABEL: Record<string, string> = {
  before_char: '角色定义之前',
  after_char: '角色定义之后',
  before_example: '示例之前',
  after_example: '示例之后',
  at_depth: '按深度插入',
};

/** 三态图例：状态一律"图标 + 文字"，禁止仅靠颜色表达 */
export function HitTestLegend({ className }: { className?: string }) {
  const states: EntryState[] = ['hit_in_budget', 'hit_evicted', 'miss'];
  return (
    <div className={cn('flex flex-wrap items-center gap-x-4 gap-y-1.5', className)}>
      {states.map((s) => {
        const { label, Icon, tone } = STATE_META[s];
        return (
          <span key={s} className="inline-flex items-center gap-1.5 text-sm text-fg-2">
            <Icon className={cn('size-3.5', tone)} aria-hidden="true" />
            {label}
          </span>
        );
      })}
    </div>
  );
}

interface HitTestPanelProps {
  /** 条目总数（未跑测试时用于展示说明） */
  entryCount: number;
  result: WorldBookTestResult | null;
  loading: boolean;
  onRun: (sampleText: string) => void;
  /** 后端不可用时禁用，并给出原因 */
  disabled?: boolean;
  disabledReason?: string;
}

/**
 * 世界书命中测试面板（docs/03-uiux.md §7.4 的落点）。
 * 输入一段"最近对话"样例文本 → 逐条返回命中/未命中/被预算挤出。
 */
export function HitTestPanel({
  entryCount,
  result,
  loading,
  onRun,
  disabled,
  disabledReason,
}: HitTestPanelProps) {
  const [sample, setSample] = useState('');

  const states = result
    ? result.entries.reduce(
        (acc, e) => {
          acc[entryState(e)] += 1;
          return acc;
        },
        { miss: 0, hit_in_budget: 0, hit_evicted: 0 } as Record<EntryState, number>,
      )
    : null;

  const usedPct =
    result && result.token_budget > 0
      ? Math.min(100, Math.round((result.total_tokens / result.token_budget) * 100))
      : 0;

  return (
    <section aria-labelledby="hit-test-title" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id="hit-test-title" className="title-section flex items-center gap-2 text-fg">
          <KeyRound className="size-4 text-muted" aria-hidden="true" />
          命中测试
        </h3>
        <span className="tech-meta">{entryCount} 条条目</span>
      </div>

      <p className="text-sm leading-relaxed text-muted">
        粘贴一段<strong className="font-medium text-fg-2">最近会发生的话</strong>（例如你准备发的那句），
        下面会逐条告诉你：哪条被触发、命中了哪个关键词、是否挤进了这次上下文的预算。
      </p>

      <Textarea
        value={sample}
        onChange={(e) => setSample(e.target.value)}
        placeholder={'例如：你把怀表放回口袋，问老周的豆浆摊今天还出吗'}
        aria-label="用于模拟最近对话的样例文本"
        className="min-h-16"
      />

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="primary"
          onClick={() => onRun(sample)}
          loading={loading}
          disabled={disabled || sample.trim().length === 0}
        >
          <Sparkles className="size-4" aria-hidden="true" />
          跑一次命中测试
        </Button>
        {sample ? (
          <Button variant="ghost" onClick={() => setSample('')}>
            清空
          </Button>
        ) : null}
      </div>

      {disabled && disabledReason ? (
        <p className="text-sm leading-relaxed text-warn">{disabledReason}</p>
      ) : null}

      <Separator />

      {!result ? (
        <EmptyState
          size="compact"
          icon={Filter}
          title="还没有测试结果"
          description="命中测试不会改动世界书，也不会调用模型——它只是把引擎的判断过程摊开给你看。"
          hint="提示：包含「怀表」「豆浆」等关键词，会看到不同条目分别落入三种状态。"
        />
      ) : (
        <div className="space-y-3">
          <HitTestLegend />

          {/* 预算占用 */}
          <div className="rounded-md border border-border bg-surface p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 label-caps">
                <Coins className="size-3.5" aria-hidden="true" />
                Token 预算
              </span>
              <span className="tech-meta">
                {result.total_tokens} / {result.token_budget}
              </span>
            </div>
            <div
              className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken"
              role="img"
              aria-label={`已用 ${usedPct}% 的世界书 token 预算`}
            >
              <div className="h-full rounded-full bg-accent" style={{ width: `${usedPct}%` }} />
            </div>
            {states && states.hit_evicted > 0 ? (
              <p className="mt-2 text-sm leading-relaxed text-warn">
                有 {states.hit_evicted} 条命中了但没挤进预算。提高世界书的 token 预算，或降低这几条的优先级之外的内容长度，就能让它们进来。
              </p>
            ) : null}
          </div>

          {/* 逐条判定 */}
          <ul className="space-y-2">
            {result.entries.map((entry) => {
              const state = entryState(entry);
              const meta = STATE_META[state];
              const Icon = meta.Icon;
              return (
                <li key={entry.entry_id} className={cn('rounded-md border p-3', meta.row)}>
                  <div className="flex items-start gap-2.5">
                    <Icon className={cn('mt-0.5 size-4 shrink-0', meta.tone)} aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="min-w-0 truncate text-base font-medium text-fg">
                          {entry.comment}
                        </span>
                        <Badge variant={meta.badge}>{meta.label}</Badge>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
                        <span>
                          匹配方式：
                          <span className="text-fg-2">{MATCH_TYPE_LABEL[entry.match_type]}</span>
                        </span>
                        {entry.matched_key ? (
                          <span className="font-mono text-xs tabular-nums text-fg-2">
                            命中关键词「{entry.matched_key}」
                          </span>
                        ) : null}
                        <span className="font-mono text-xs tabular-nums text-meta">
                          {entry.token_count} tok
                        </span>
                        <span>
                          插入位置：
                          <span className="text-fg-2">
                            {entry.final_position
                              ? POSITION_LABEL[entry.final_position] ?? entry.final_position
                              : '未注入'}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
