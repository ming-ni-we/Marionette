import { useState } from 'react';
import { cn, copyText } from '@/lib/utils';
import { toast } from '@/stores/ui';
import { Button } from '@/components/ui/button';
import { Hint } from '@/components/ui/tooltip';
import { Pencil, Copy, GitFork, RefreshCw, ArrowLeftRight, CircleCheck } from '@/components/icons';
import type { Message } from '@/api/types';

interface MessageBubbleProps {
  message: Message;
  /** 角色名（assistant 头像位） */
  speakerName: string;
  /** 该条是否可换一条（swipe 备选数 > 1 时显示） */
  swipeCount?: number;
  onRegenerate?: (messageId: string) => void;
  onFork?: (messageId: string) => void;
  onEdit?: (messageId: string, content: string) => void;
  /** 正在生成中的流式消息 */
  streaming?: boolean;
}

/**
 * 会话气泡。
 * 角色消息（左）：Serif 叙事正文 + 1.75 行高 + 低对比背景 --color-reading-surface。
 * 用户消息（右）：轻气泡，Sans，克制。
 * 元信息操作默认收起为 hover/focus 才出现，避免打断沉浸。
 */
export function MessageBubble({
  message,
  speakerName,
  swipeCount = 1,
  onRegenerate,
  onFork,
  onEdit,
  streaming = false,
}: MessageBubbleProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system' || message.role === 'tool';

  const handleCopy = async () => {
    const ok = await copyText(message.content);
    if (ok) toast.success('已复制这条消息');
    else toast.danger('复制失败', '当前浏览器不允许访问剪贴板');
  };

  if (isSystem) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-meta">
        <span className="h-px flex-1 bg-border-soft" />
        <span className="max-w-[60ch] truncate">{message.content}</span>
        <span className="h-px flex-1 bg-border-soft" />
      </div>
    );
  }

  return (
    <article
      className={cn('group/message flex gap-3 py-3', isUser && 'flex-row-reverse')}
      aria-label={isUser ? '你的消息' : `${speakerName} 的消息`}
    >
      {/* 头像位：文字首字（无图时不使用通用蛋形头像占位） */}
      <div
        aria-hidden="true"
        className={cn(
          'grid size-7 shrink-0 place-items-center rounded-md border text-xs font-medium',
          isUser
            ? 'border-border bg-surface-warm text-muted'
            : 'border-border bg-surface text-accent',
        )}
      >
        {isUser ? '你' : speakerName.slice(0, 1)}
      </div>

      <div className={cn('min-w-0 flex-1', isUser && 'flex flex-col items-end')}>
        {!isUser ? (
          <div className="mb-1 flex items-center gap-2">
            <span className="text-sm font-medium text-fg-2">{speakerName}</span>
            {message.status === 'incomplete' ? (
              <span className="text-xs text-warn">生成未完成</span>
            ) : null}
            {streaming ? <span className="text-xs text-meta">生成中…</span> : null}
          </div>
        ) : null}

        {editing ? (
          <div className="w-full max-w-[68ch] space-y-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="编辑消息内容"
              className="min-h-24 w-full resize-y rounded-md border border-border bg-surface-sunken px-3 py-2 text-base leading-reading text-fg focus-visible:border-accent"
            />
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  onEdit?.(message.id, draft);
                  setEditing(false);
                }}
              >
                保存修改
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setDraft(message.content);
                  setEditing(false);
                }}
              >
                取消
              </Button>
            </div>
          </div>
        ) : (
          <div
            className={cn(
              'max-w-[68ch] rounded-lg border px-3.5 py-2.5',
              isUser
                ? 'border-border bg-surface'
                : 'border-border-soft bg-reading-surface',
            )}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap text-base leading-relaxed text-fg">{message.content}</p>
            ) : (
              <p className={cn('narrative', streaming && 'stream-caret')}>{message.content}</p>
            )}
          </div>
        )}

        {/* 元信息操作：默认弱化，hover/focus-within 才升亮 */}
        {!editing ? (
          <div
            className={cn(
              'mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity duration-[var(--dur-fast)] group-hover/message:opacity-100 focus-within:opacity-100',
              isUser && 'flex-row-reverse',
            )}
          >
            <Hint label="编辑这条消息">
              <Button variant="ghost" size="icon-sm" aria-label="编辑这条消息" onClick={() => setEditing(true)}>
                <Pencil className="size-3.5" aria-hidden="true" />
              </Button>
            </Hint>
            <Hint label="复制内容">
              <Button variant="ghost" size="icon-sm" aria-label="复制这条消息" onClick={handleCopy}>
                <Copy className="size-3.5" aria-hidden="true" />
              </Button>
            </Hint>
            {!isUser && onRegenerate ? (
              <Hint label="重新生成这一条（保留原结果作为备选）">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="重新生成这一条"
                  onClick={() => onRegenerate(message.id)}
                >
                  <RefreshCw className="size-3.5" aria-hidden="true" />
                </Button>
              </Hint>
            ) : null}
            {!isUser && onFork ? (
              <Hint label="从这里分叉出一条新会话，原会话不受影响">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="从这条消息分叉"
                  onClick={() => onFork(message.id)}
                >
                  <GitFork className="size-3.5" aria-hidden="true" />
                </Button>
              </Hint>
            ) : null}
            {swipeCount > 1 ? (
              <span className="inline-flex items-center gap-1 px-1 tech-meta">
                <ArrowLeftRight className="size-3" aria-hidden="true" />
                1/{swipeCount}
              </span>
            ) : null}
            {message.token_count ? (
              <span className="px-1 tech-meta">
                <CircleCheck className="mr-0.5 inline size-3 align-[-2px]" aria-hidden="true" />
                {message.token_count} tok
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
