import { cn, truncate } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/common/empty-state';
import { GitBranch, GitFork, CornerUpLeft, UserRound, Sparkles } from '@/components/icons';
import type { Message } from '@/api/types';

interface BranchTreeProps {
  messages: Message[];
  /** 当前阅读位置（最后一条） */
  currentMessageId?: string;
  onFork: (messageId: string) => void;
  onJump: (messageId: string) => void;
  /** 由本会话派生出的分支数（来自 sessions 列表，可选） */
  childBranches?: Array<{ id: string; title: string }>;
}

/**
 * 会话树视图（docs/03-uiux.md §7.3）。
 * 时间线缩略 + 任意节点"分叉/回到此处"。让"分支"成为一等公民。
 */
export function BranchTree({ messages, currentMessageId, onFork, onJump, childBranches = [] }: BranchTreeProps) {
  if (messages.length === 0) {
    return (
      <EmptyState
        size="compact"
        icon={GitBranch}
        title="这场会话还没有可回溯的节点"
        description="发出第一条消息之后，这里会按顺序列出每个可回溯的位置，你可以在任意一处开出一条新的故事线。"
        hint="分支不会修改当前会话——原会话保持原样。"
      />
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm leading-relaxed text-muted">
        在任意节点分叉，会<strong className="font-medium text-fg-2">复制到这里为止的内容</strong>
        生成一场可独立继续的新会话；当前会话不受影响。
      </p>

      <ol className="relative space-y-0.5 pl-5">
        <span
          aria-hidden="true"
          className="absolute left-[7px] top-2 bottom-2 w-px bg-border"
        />
        {messages.map((msg, index) => {
          const isCurrent = msg.id === currentMessageId;
          const isUser = msg.role === 'user';
          return (
            <li key={msg.id} className="relative">
              <span
                aria-hidden="true"
                className={cn(
                  'absolute -left-[17px] top-2.5 size-3 rounded-full border-2 border-surface',
                  isCurrent ? 'bg-accent' : 'bg-border-strong',
                )}
              />
              <div
                className={cn(
                  'group/node rounded-md border px-2.5 py-2 motion-fast',
                  isCurrent ? 'border-border-strong bg-surface-warm' : 'border-transparent hover:border-border hover:bg-surface-warm',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="tech-meta">#{String(index + 1).padStart(3, '0')}</span>
                  {isUser ? (
                    <UserRound className="size-3.5 text-muted" aria-hidden="true" />
                  ) : (
                    <Sparkles className="size-3.5 text-accent" aria-hidden="true" />
                  )}
                  <span className="text-xs text-muted">{isUser ? '你' : '角色'}</span>
                  {isCurrent ? <span className="tech-meta text-accent">当前位置</span> : null}
                </div>
                <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-fg-2">
                  {truncate(msg.content.replace(/\s+/g, ' '), 86)}
                </p>
                <div className="mt-1.5 flex items-center gap-1 opacity-0 transition-opacity duration-[var(--dur-fast)] group-hover/node:opacity-100 focus-within:opacity-100">
                  <Button variant="ghost" size="sm" onClick={() => onFork(msg.id)} className="gap-1.5">
                    <GitFork className="size-3.5" aria-hidden="true" />
                    从这里分叉
                  </Button>
                  {!isCurrent ? (
                    <Button variant="ghost" size="sm" onClick={() => onJump(msg.id)} className="gap-1.5">
                      <CornerUpLeft className="size-3.5" aria-hidden="true" />
                      回到此处
                    </Button>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="space-y-2 border-t border-border-soft pt-3">
        <h4 className="label-caps">已派生出的分支会话</h4>
        {childBranches.length === 0 ? (
          <p className="text-sm leading-relaxed text-muted">
            还没有分支。想试另一条走法时，用上面的「从这里分叉」——比重新开一场省事得多。
          </p>
        ) : (
          <ul className="space-y-1">
            {childBranches.map((b) => (
              <li key={b.id} className="flex items-center gap-2 rounded-sm border border-border-soft px-2 py-1.5 text-sm">
                <GitBranch className="size-3.5 shrink-0 text-muted" aria-hidden="true" />
                <span className="min-w-0 truncate text-fg-2">{b.title}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
