import type { Message, SessionState } from '@/api/types';
import { STATE_LABEL } from '@/mocks/fixtures';
import { MessageBubble } from '@/components/session/message-bubble';
import { EmptyState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import { toast } from '@/stores/ui';
import { MessageSquare, Sparkles, BookOpen, CircleAlert, RefreshCw } from '@/components/icons';

/** 阅读列：68ch 单列 + 衬线叙事（SPEC §10）+ 生成中/错误就地状态 */
export function ReadingColumn({
  messages,
  speakerName,
  state,
  generating,
  error,
  hasOpening,
  onRegenerate,
  onFork,
  onRetry,
}: {
  messages: Message[];
  speakerName: string;
  state: SessionState;
  generating: boolean;
  error: string | null;
  hasOpening: boolean;
  onRegenerate: (message: Message) => void;
  onFork: (messageId: string) => void;
  onRetry: () => void;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-[68ch] px-4 py-4">
        {messages.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="这一场还没有消息"
            description="下面输入框里写第一句话就能开始。角色卡的开场白会自动成为对话的起点；世界书与记忆会在你发言后开始工作。"
            actions={
              <Button
                variant="secondary"
                onClick={() => {
                  if (hasOpening) {
                    toast.show('已把开场白放回阅读列', '它是这场会话原本的起点。');
                  } else {
                    toast.show('这张卡没有开场白', '直接写你的第一句即可。');
                  }
                }}
              >
                <Sparkles className="size-4" aria-hidden="true" />
                看看这张卡的开场白
              </Button>
            }
            hint={
              <span className="inline-flex items-center gap-1.5">
                <BookOpen className="size-3.5" aria-hidden="true" />
                想看引擎怎么组装上下文？生成一轮之后打开「上下文检视」。
              </span>
            }
          />
        ) : (
          <div>
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                speakerName={speakerName}
                streaming={msg.status === 'streaming'}
                onRegenerate={() => onRegenerate(msg)}
                onFork={onFork}
              />
            ))}
          </div>
        )}

        {/* 生成中：占位（预留行高，不抖动） */}
        {generating ? (
          <p className="py-2 text-sm text-accent" aria-live="polite">
            {state === 'assembling' ? '正在装配上下文…' : `${STATE_LABEL[state]}…`}
          </p>
        ) : null}

        {/* 就地错误条：已生成内容保留不丢 */}
        {error ? (
          <div
            role="alert"
            className="mt-3 flex flex-wrap items-center gap-3 rounded-md border border-border bg-danger-subtle px-3 py-2.5"
          >
            <CircleAlert className="size-4 shrink-0 text-danger" aria-hidden="true" />
            <span className="min-w-0 flex-1 text-sm leading-relaxed text-fg-2">
              {error} —— 已生成的内容保留在上面，不会丢。
            </span>
            <Button variant="secondary" size="sm" onClick={onRetry}>
              <RefreshCw className="size-4" aria-hidden="true" />
              重试这一轮
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
