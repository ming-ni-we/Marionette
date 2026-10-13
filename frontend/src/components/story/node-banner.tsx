import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { GitBranch, Sparkles } from '@/components/icons';
import type { SseEventMap } from '@/api/types';

type NodeEvent = SseEventMap['node'];

interface NodeBannerProps {
  nodes: NodeEvent[];
  className?: string;
}

/**
 * 剧情节点横幅。
 * -----------------------------------------------------------------------------
 * 节点是**幕结构**上的事件（"账本现身"、"公告倒计时"），不是角色说的话，
 * 所以它不进入阅读列的正常流，而是浮在阅读列顶部作为一次性的「剧情推进」提示。
 *
 * 多条节点同一轮触发时叠成一行 chips，不竖排——竖排会挤占阅读空间，
 * 而节点本身只承担「告诉你故事动了」这一件事。
 */
export function NodeBanner({ nodes, className }: NodeBannerProps) {
  if (nodes.length === 0) return null;

  return (
    <div
      className={cn(
        'border-b border-border-soft bg-accent-subtle px-4 py-2',
        className,
      )}
      role="status"
    >
      <div className="mx-auto flex w-full max-w-[68ch] flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-accent">
          <GitBranch className="size-3.5" aria-hidden="true" />
          剧情节点
        </span>

        {nodes.map((node) => (
          <span key={node.id} className="inline-flex min-w-0 items-center gap-1.5">
            <Badge variant="accent">{node.title || node.id}</Badge>
            {node.brief ? (
              <span className="truncate text-xs leading-relaxed text-fg-2">{node.brief}</span>
            ) : null}
          </span>
        ))}

        <span className="ml-auto inline-flex shrink-0 items-center gap-1 text-xs text-meta">
          <Sparkles className="size-3" aria-hidden="true" />
          已写入剧情状态，后续角色会记得
        </span>
      </div>
    </div>
  );
}
