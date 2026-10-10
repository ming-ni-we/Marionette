import { useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Hint } from '@/components/ui/tooltip';
import { Send, Square, Terminal, ChevronDown } from '@/components/icons';

interface ComposerProps {
  onSend: (text: string, narration: string) => void;
  onStop: () => void;
  generating: boolean;
  disabled?: boolean;
  disabledReason?: string;
  placeholder?: string;
}

/**
 * 会话输入区（底部 dock）。
 * 「旁白 / 指令」区默认折叠——展开才出现，避免污染沉浸态（docs/03-uiux.md §7.3）。
 */
export function Composer({
  onSend,
  onStop,
  generating,
  disabled,
  disabledReason,
  placeholder = '写点什么…（Enter 发送，Shift+Enter 换行）',
}: ComposerProps) {
  const [text, setText] = useState('');
  const [narrationOpen, setNarrationOpen] = useState(false);
  const [narration, setNarration] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const grow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const canSend = !disabled && !generating && text.trim().length > 0;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim(), narration.trim());
    setText('');
    setNarration('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.focus();
    }
  };

  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto w-full max-w-[68ch] space-y-2">
        {disabled && disabledReason ? (
          <p className="text-sm leading-relaxed text-warn">{disabledReason}</p>
        ) : null}

        {/* 旁白 / 指令（默认折叠） */}
        <div>
          <button
            type="button"
            aria-expanded={narrationOpen}
            onClick={() => setNarrationOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-sm px-1.5 py-1 text-xs text-muted motion-fast hover:bg-surface-warm hover:text-fg-2"
          >
            <ChevronDown
              className={cn('size-3.5 motion-fast', narrationOpen && 'rotate-180')}
              aria-hidden="true"
            />
            <Terminal className="size-3.5" aria-hidden="true" />
            旁白 / 指令
            <span className="text-meta">（写给引擎，不会当成台词）</span>
          </button>
          {narrationOpen ? (
            <textarea
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
              placeholder="例如：让苏晚注意到我手上的划痕；保持节奏慢一些。"
              aria-label="旁白或指令"
              rows={2}
              className="mt-1.5 w-full resize-y rounded-sm border border-border bg-surface-sunken px-3 py-2 text-sm leading-relaxed text-fg-2 placeholder:text-muted focus-visible:border-accent"
            />
          ) : null}
        </div>

        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              grow(e.target);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={placeholder}
            aria-label="输入消息"
            rows={1}
            disabled={disabled}
            className="min-h-9 w-full resize-none rounded-md border border-border bg-surface-sunken px-3 py-2 text-base leading-relaxed text-fg placeholder:text-muted motion-fast hover:border-border-strong focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-50"
          />

          {generating ? (
            <Hint label="立即中止生成（已生成内容会保留）">
              <Button variant="danger" size="icon" aria-label="停止生成" onClick={onStop}>
                <Square className="size-4" aria-hidden="true" />
              </Button>
            </Hint>
          ) : (
            <Button
              variant="primary"
              size="icon"
              aria-label="发送消息"
              disabled={!canSend}
              onClick={submit}
            >
              <Send className="size-4" aria-hidden="true" />
            </Button>
          )}
        </div>

        <div className="flex items-center justify-between">
          <span className="tech-meta">
            {text.length > 0 ? `${text.length} 字` : '支持中文 · 输出附带 AI 生成内容标识'}
          </span>
          {generating ? (
            <span className="text-xs text-accent" aria-live="polite">
              流式生成中，可随时中止
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
