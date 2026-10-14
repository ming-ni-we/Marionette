import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Hint } from '@/components/ui/tooltip';
import { EmptyState } from '@/components/common/empty-state';
import {
  Eye,
  MessageSquare,
  Play,
  Send,
  Square,
  Compass,
  BookOpen,
  Sparkles,
  CircleAlert,
  RefreshCw,
} from '@/components/icons';
import type { ActionSuggestion, ActionTone } from '@/api/types';

/**
 * `tone` → 图标 + 语义色。
 * 图标只做「一眼分类」的辅助，绝不能是唯一区分手段——所以按钮上永远有 `label` 文案。
 */
const TONE_META: Record<ActionTone, { Icon: typeof Eye; label: string; toneClass: string }> = {
  observe: { Icon: Eye, label: '观察', toneClass: 'text-info' },
  speak: { Icon: MessageSquare, label: '发言', toneClass: 'text-accent' },
  act: { Icon: Play, label: '行动', toneClass: 'text-success' },
  move: { Icon: Compass, label: '移动', toneClass: 'text-warn' },
};

interface ActionDockProps {
  /** 本轮导演给出的行动建议（空数组 → 降级为纯输入框） */
  suggestions: ActionSuggestion[];
  onSend: (text: string) => void;
  onStop: () => void;
  /** 生成中：建议与输入一并禁用 */
  generating: boolean;
  /** 整场不可用（已归档等） */
  disabled?: boolean;
  disabledReason?: string;
  error?: string | null;
  onRetry?: () => void;
}

/**
 * 行动建议 Dock（剧情模式底部输入区）。
 * -----------------------------------------------------------------------------
 * 与 1v1 `Composer` 的关键差别：
 *   1) **建议优先**——玩家多数时候不该打字，点一下就够了（降低「不知道该说什么」的摩擦）
 *   2) **输入永远可用**——建议框不是唯一出口；无建议时也不能出现空死区
 *   3) 不接受 `narration` 第二参（那是 1v1 的「写给引擎」通道，剧情模式由导演接管）
 */
export function ActionDock({
  suggestions,
  onSend,
  onStop,
  generating,
  disabled,
  disabledReason,
  error,
  onRetry,
}: ActionDockProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 发送后把焦点收回输入框，连续游玩时不用每次点回来
  useEffect(() => {
    if (!generating && textareaRef.current) textareaRef.current.focus();
  }, [generating]);

  const canSend = !disabled && !generating && text.trim().length > 0;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  /**
   * 单击建议 = **预填**到输入框（S15-2）。
   *
   * 此前是 `onSend(s.label)` 直接发 —— 芯片本体就代表"这轮走这条路"，玩家
   * 一点就被推着走，想加半句台词都来不及。改为预填后可编辑：想照做就回车，
   * 想补一句就接着写。**直发保留为双击 / ⚡ 按钮**（老玩家的肌肉记忆 + 快路径）。
   */
  const pick = (s: ActionSuggestion) => {
    if (disabled || generating) return;
    setText(s.label);
    // 焦点交还输入框，光标落到末尾 —— 预填的意义就在于"接着改"
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    });
  };

  /** 直发（双击 / ⚡）：跳过编辑，一步走完。 */
  const pickAndSend = (s: ActionSuggestion) => {
    if (disabled || generating) return;
    onSend(s.label);
    setText('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const blocked = Boolean(disabled) || generating;

  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto w-full max-w-[68ch] space-y-2.5">
        {disabled && disabledReason ? (
          <p className="text-sm leading-relaxed text-warn">{disabledReason}</p>
        ) : null}

        {/* ---- 行动建议 ---- */}
        {suggestions.length > 0 ? (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <Sparkles className="size-3.5 text-accent" aria-hidden="true" />
              <span className="text-xs font-medium text-fg-2">导演给了几个方向</span>
              <span className="text-xs text-meta">
                （点一下填进输入框再改，双击或按 ➤ 直接走）
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="行动建议">
              {suggestions.map((s) => (
                <SuggestionButton
                  key={s.id}
                  suggestion={s}
                  disabled={blocked}
                  onPick={() => pick(s)}
                  onPickAndSend={() => pickAndSend(s)}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-md border border-border-soft bg-surface-sunken px-3 py-2">
            {generating ? (
              <p className="text-sm text-accent" aria-live="polite">
                导演正在安排这一轮，稍后会给出几个方向。
              </p>
            ) : (
              <p className="text-sm leading-relaxed text-muted">
                这一轮没有给建议 —— 直接写你想做什么、说什么就行。
              </p>
            )}
          </div>
        )}

        {/* ---- 自由输入 ---- */}
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              e.target.style.height = 'auto';
              e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={
              disabled
                ? '这一场已经不能继续了'
                : generating
                  ? '等角色把这一轮说完…'
                  : '你想做什么、说什么？（Enter 发送，Shift+Enter 换行）'
            }
            aria-label="输入你的行动"
            rows={1}
            disabled={Boolean(disabled)}
            className="min-h-9 w-full resize-none rounded-md border border-border bg-surface-sunken px-3 py-2 text-base leading-relaxed text-fg placeholder:text-muted motion-fast hover:border-border-strong focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-50"
          />

          {generating ? (
            <Hint label="立即中止这一轮（已生成的内容会保留）">
              <Button variant="danger" size="icon" aria-label="停止生成" onClick={onStop}>
                <Square className="size-4" aria-hidden="true" />
              </Button>
            </Hint>
          ) : (
            <Button
              variant="primary"
              size="icon"
              aria-label="发送你的行动"
              disabled={!canSend}
              onClick={submit}
            >
              <Send className="size-4" aria-hidden="true" />
            </Button>
          )}
        </div>

        <div className="flex items-center justify-between gap-3">
          <span className="tech-meta">
            {text.length > 0 ? `${text.length} 字` : '旁白由导演代写 · 输出附带 AI 生成内容标识'}
          </span>
          {generating ? (
            <span className="text-xs text-accent" aria-live="polite">
              多角色轮流演出中，可随时中止
            </span>
          ) : null}
        </div>

        {/* ---- 就地错误条（与 1v1 一致：不丢已生成内容） ---- */}
        {error ? (
          <div
            role="alert"
            className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-danger-subtle px-3 py-2.5"
          >
            <CircleAlert className="size-4 shrink-0 text-danger" aria-hidden="true" />
            <span className="min-w-0 flex-1 text-sm leading-relaxed text-fg-2">
              {error} —— 已经演出来的部分保留在上面。
            </span>
            {onRetry ? (
              <Button variant="secondary" size="sm" onClick={onRetry}>
                <RefreshCw className="size-4" aria-hidden="true" />
                重试这一轮
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/**
 * 单条建议芯片（S15-2）。
 *
 * 三种交互，各有明确入口 —— 不让玩家去猜：
 *   - **单击** → 预填到输入框（主路径：多数人想改一两个字再发）
 *   - **双击** → 直接发送（快路径，点击类操作，不依赖键盘）
 *   - **➤ 小按钮** → 直接发送（显式入口：触屏没有"双击"语义，无障碍也读不出来）
 *
 * 文案永远在，图标只做分类辅助。
 */
function SuggestionButton({
  suggestion,
  disabled,
  onPick,
  onPickAndSend,
}: {
  suggestion: ActionSuggestion;
  disabled: boolean;
  onPick: () => void;
  onPickAndSend: () => void;
}) {
  const meta = TONE_META[suggestion.tone ?? 'act'];
  const { Icon } = meta;

  return (
    <span
      className={cn(
        'group/action inline-flex max-w-full items-center gap-1 rounded-md border border-border bg-surface pr-1 pl-2.5 py-1.5',
        'motion-fast hover:border-border-strong hover:bg-surface-warm',
        'focus-within:border-accent',
        disabled && 'opacity-45',
      )}
    >
      {/* 主体：单击预填、双击直发。
          ⚠️ 双击前浏览器**必然**先派发一次 click（预填）——这是可接受的：
          视觉上表现为"填进去 → 立刻发出"，正文不会出现两次。 */}
      <button
        type="button"
        onClick={onPick}
        onDoubleClick={onPickAndSend}
        disabled={disabled}
        title={suggestion.hint || `${meta.label}：${suggestion.label}`}
        className={cn(
          'inline-flex min-w-0 items-center gap-1.5 text-left text-sm leading-snug text-fg-2',
          'hover:text-fg focus-visible:outline-none',
          'disabled:cursor-not-allowed disabled:hover:text-fg-2',
        )}
      >
        <Icon className={cn('size-3.5 shrink-0', meta.toneClass)} aria-hidden="true" />
        <span className="min-w-0">
          <span className="block truncate font-medium">{suggestion.label}</span>
          {suggestion.hint ? (
            <span className="mt-0.5 block truncate text-xs text-meta">{suggestion.hint}</span>
          ) : null}
        </span>
      </button>

      {/* 直发。stopPropagation：否则会连带触发主体的 click（多一次预填，无害但脏） */}
      <button
        type="button"
        aria-label={`直接发送：${suggestion.label}`}
        title="直接发送"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          onPickAndSend();
        }}
        className={cn(
          'ml-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded text-meta',
          'motion-fast hover:bg-accent-subtle hover:text-accent focus-visible:text-accent focus-visible:outline-none',
          'disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-meta',
        )}
      >
        <Send className="size-3" aria-hidden="true" />
      </button>
    </span>
  );
}

/** 空态：整场一条建议都没有、也不该发呆时用（例如剧情已结束）。 */
export function ActionDockEmpty({ title, description }: { title: string; description: string }) {
  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto w-full max-w-[68ch]">
        <EmptyState size="compact" icon={BookOpen} title={title} description={description} />
      </div>
    </div>
  );
}
