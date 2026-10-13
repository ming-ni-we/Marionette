import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/common/empty-state';
import { entryState, HitTestLegend } from '@/components/worldbook/hit-test-panel';
import { Gauge, Layers, RefreshCw, Terminal, CircleCheck, CircleX, TriangleAlert } from '@/components/icons';
import type { ContextSegmentName, ContextSnapshot } from '@/api/types';

const SEGMENT_LABEL: Record<ContextSegmentName, string> = {
  system: '系统基座',
  character: '角色定义',
  world_info_before: '世界书 · 角色定义前',
  memory: '长期记忆（摘要 + 事实）',
  vector_recall: '向量召回',
  examples: '示例对话',
  history: '历史消息',
  world_info_at_depth: '世界书 · 按深度插入',
  post_history: '历史后指令',
  /* ---- 剧情模式新增（1v1 下 token 恒为 0，不渲染）---- */
  story_state: '剧情状态（幕 · 拍点 · 旗标）',
  relations: '角色关系图',
  cast_roster: '在场角色',
};

const STATE_ICON = {
  hit_in_budget: { Icon: CircleCheck, tone: 'text-success', label: '命中 · 已注入' },
  hit_evicted: { Icon: TriangleAlert, tone: 'text-warn', label: '命中 · 被预算挤出' },
  miss: { Icon: CircleX, tone: 'text-meta', label: '未命中' },
} as const;

interface ContextInspectionProps {
  snapshot: ContextSnapshot | null;
  loading: boolean;
  onLoad: () => void;
}

/**
 * 上下文检视（docs/03-uiux.md §7.4）。
 * 把"上一轮真实组装的 prompt"摊开：分段 token 占用 + 世界书触发 trace + 估算/实际对账。
 * 这是把酒馆"调参靠玄学"转成"看得见因果"的关键面板。
 */
export function ContextInspection({ snapshot, loading, onLoad }: ContextInspectionProps) {
  if (!snapshot) {
    return (
      <div className="space-y-3">
        <EmptyState
          size="compact"
          icon={Layers}
          title="还没有可检视的上下文"
          description="上下文检视读取的是「上一轮真实发给模型的内容」——所以要先在这个会话里成功生成过一次，这里才会有东西。"
          actions={
            <Button variant="secondary" onClick={onLoad} loading={loading}>
              <RefreshCw className="size-4" aria-hidden="true" />
              读取上一轮上下文
            </Button>
          }
        />
      </div>
    );
  }

  const maxTok = Math.max(1, ...snapshot.segments.map((s) => s.token_count));
  const { budget } = snapshot;
  const usedPct =
    budget.max_context_tokens > 0
      ? Math.min(100, Math.round((budget.used_tokens / budget.max_context_tokens) * 100))
      : 0;
  const drift =
    snapshot.actual_prompt_tokens != null
      ? snapshot.actual_prompt_tokens - snapshot.estimated_prompt_tokens
      : null;

  return (
    <div className="space-y-4">
      {/* 预算总览 */}
      <section className="rounded-md border border-border bg-surface p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 label-caps">
            <Gauge className="size-3.5" aria-hidden="true" />
            上下文预算
          </span>
          <span className="tech-meta">
            {budget.used_tokens} / {budget.max_context_tokens}
          </span>
        </div>
        <div
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken"
          role="img"
          aria-label={`上下文已占用 ${usedPct}%`}
        >
          <div className="h-full rounded-full bg-accent" style={{ width: `${usedPct}%` }} />
        </div>
        <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
          <div>
            <dt className="text-meta">预留输出</dt>
            <dd className="font-mono text-xs tabular-nums text-fg-2">{budget.reserve_for_output}</dd>
          </div>
          <div>
            <dt className="text-meta">估算 prompt</dt>
            <dd className="font-mono text-xs tabular-nums text-fg-2">
              {snapshot.estimated_prompt_tokens}
            </dd>
          </div>
          <div>
            <dt className="text-meta">实际 prompt</dt>
            <dd className="font-mono text-xs tabular-nums text-fg-2">
              {snapshot.actual_prompt_tokens ?? '—'}
              {drift != null ? (
                <span className={cn('ml-1', Math.abs(drift) > 40 ? 'text-warn' : 'text-meta')}>
                  ({drift >= 0 ? '+' : ''}
                  {drift})
                </span>
              ) : null}
            </dd>
          </div>
        </dl>
      </section>

      {/* 分段占用 */}
      <section className="space-y-2">
        <h4 className="label-caps">分段占用</h4>
        <ul className="space-y-1.5">
          {snapshot.segments
            .filter((s) => s.token_count > 0)
            .map((seg) => (
              <li key={seg.name}>
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="truncate text-fg-2">{SEGMENT_LABEL[seg.name]}</span>
                  <span className="shrink-0 font-mono text-xs tabular-nums text-meta">
                    {seg.token_count} tok
                  </span>
                </div>
                <div
                  className="mt-1 h-1 w-full overflow-hidden rounded-full bg-surface-sunken"
                  role="img"
                  aria-label={`${SEGMENT_LABEL[seg.name]} 占用 ${seg.token_count} token`}
                >
                  <div
                    className="h-full rounded-full bg-border-strong"
                    style={{ width: `${Math.round((seg.token_count / maxTok) * 100)}%` }}
                  />
                </div>
              </li>
            ))}
        </ul>
      </section>

      {/* 世界书触发轨迹 */}
      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h4 className="label-caps">世界书触发轨迹</h4>
        </div>
        {snapshot.world_info_trace.length === 0 ? (
          <p className="text-sm leading-relaxed text-muted">
            这一轮没有任何世界书条目参与。若你预期某条应该触发，去世界书编辑器跑一次命中测试，
            用同一段文本对照关键词。
          </p>
        ) : (
          <>
            <HitTestLegend />
            <ul className="space-y-1.5">
              {snapshot.world_info_trace.map((entry) => {
                const state = entryState(entry);
                const { Icon, tone, label } = STATE_ICON[state];
                return (
                  <li
                    key={entry.entry_id}
                    className="flex items-start gap-2 rounded-sm border border-border-soft px-2 py-1.5"
                  >
                    <Icon className={cn('mt-0.5 size-3.5 shrink-0', tone)} aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-fg">{entry.comment}</span>
                      <span className="mt-0.5 block text-xs text-meta">
                        {label}
                        {entry.matched_key ? ` · 关键词「${entry.matched_key}」` : ''} ·{' '}
                        <span className="font-mono tabular-nums">{entry.token_count} tok</span>
                      </span>
                    </div>
                    {!entry.in_budget ? <Badge variant="warn">挤出</Badge> : null}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </section>

      {/* 组装后的 prompt 原文 */}
      <section className="space-y-2">
        <h4 className="flex items-center gap-1.5 label-caps">
          <Terminal className="size-3.5" aria-hidden="true" />
          组装后的 Prompt 原文
        </h4>
        <pre className="max-h-72 overflow-auto rounded-md border border-border bg-surface-sunken p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-fg-2">
          {snapshot.prompt_text}
        </pre>
        <p className="text-xs leading-relaxed text-meta">
          组装于 {new Date(snapshot.assembled_at).toLocaleString('zh-CN')}。这是逐字记录，
          可用来对照"我改了设定，模型看到的东西到底变了没有"。
        </p>
      </section>
    </div>
  );
}
