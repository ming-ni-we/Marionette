import { cn } from '@/lib/utils';
import { BookOpen, Brain, Gauge, GitBranch, Maximize2 } from '@/components/icons';
import type { SessionState } from '@/api/types';

interface IndicatorStripProps {
  worldInfoHits: number;
  memoryFactCount: number;
  usedTokens: number;
  maxTokens: number;
  branchCount: number;
  state: SessionState;
  onOpenContext: () => void;
  onOpenTree: () => void;
  onEnterImmersive: () => void;
  className?: string;
}

/**
 * 顶部细指示条（docs/03-uiux.md §7.3）。
 * 元信息默认降级为"图标 + 数字"，点击才展开右侧抽屉——绝不常驻挤压阅读列。
 */
export function IndicatorStrip({
  worldInfoHits,
  memoryFactCount,
  usedTokens,
  maxTokens,
  branchCount,
  state,
  onOpenContext,
  onOpenTree,
  onEnterImmersive,
  className,
}: IndicatorStripProps) {
  const pct = maxTokens > 0 ? Math.min(100, Math.round((usedTokens / maxTokens) * 100)) : 0;
  const generating = state === 'generating' || state === 'assembling';

  return (
    <div
      className={cn(
        'flex h-9 items-center gap-1 border-b border-border-soft bg-surface-sunken px-3',
        className,
      )}
    >
      <button
        type="button"
        onClick={onOpenContext}
        aria-label={`世界书本轮命中 ${worldInfoHits} 条，打开上下文检视`}
        className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-sm text-fg-2 motion-fast hover:bg-surface-warm hover:text-fg"
      >
        <BookOpen className="size-3.5" aria-hidden="true" />
        <span className="font-mono text-xs tabular-nums">{worldInfoHits}</span>
        <span className="hidden sm:inline">命中</span>
      </button>

      <button
        type="button"
        onClick={onOpenContext}
        aria-label={`记忆已登记 ${memoryFactCount} 条事实，打开上下文检视`}
        className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-sm text-fg-2 motion-fast hover:bg-surface-warm hover:text-fg"
      >
        <Brain className="size-3.5" aria-hidden="true" />
        <span className="font-mono text-xs tabular-nums">{memoryFactCount}</span>
        <span className="hidden sm:inline">记忆</span>
      </button>

      <button
        type="button"
        onClick={onOpenContext}
        aria-label={`上下文占用 ${pct}%，打开上下文检视`}
        className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-sm text-fg-2 motion-fast hover:bg-surface-warm hover:text-fg"
      >
        <Gauge className="size-3.5" aria-hidden="true" />
        <span className="font-mono text-xs tabular-nums">
          {usedTokens}/{maxTokens}
        </span>
        <span
          aria-hidden="true"
          className="hidden h-1 w-10 overflow-hidden rounded-full bg-surface-sunken sm:block"
        >
          <span className="block h-full bg-accent" style={{ width: `${pct}%` }} />
        </span>
      </button>

      <button
        type="button"
        onClick={onOpenTree}
        aria-label={`分支位置，共 ${branchCount} 个可回溯节点，打开分支树`}
        className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-sm text-fg-2 motion-fast hover:bg-surface-warm hover:text-fg"
      >
        <GitBranch className="size-3.5" aria-hidden="true" />
        <span className="font-mono text-xs tabular-nums">{branchCount}</span>
        <span className="hidden sm:inline">分支</span>
      </button>

      <div className="ml-auto flex items-center gap-2">
        <span
          className={cn(
            'label-caps',
            generating ? 'text-accent' : state === 'error' ? 'text-danger' : 'text-meta',
          )}
          aria-live="polite"
        >
          {state === 'idle' ? '就绪' : generating ? '生成中' : state === 'error' ? '出错' : state}
        </span>
        <button
          type="button"
          onClick={onEnterImmersive}
          aria-label="进入沉浸模式（Esc 退出）"
          className="inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-sm text-muted motion-fast hover:bg-surface-warm hover:text-fg"
        >
          <Maximize2 className="size-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">沉浸</span>
        </button>
      </div>
    </div>
  );
}
