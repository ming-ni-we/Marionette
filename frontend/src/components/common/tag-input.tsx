import { useState, type KeyboardEvent } from 'react';
import { X } from '@/components/icons';

/**
 * 标签 / 关键词输入：回车添加，退格删除末项，失焦提交。
 * 用于角色卡标签与世界书触发关键词（两者交互一致）。
 */
export function TagInput({
  tags,
  onChange,
  placeholder = '输入后回车添加',
  ariaLabel = '添加标签',
  tone = 'neutral',
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  ariaLabel?: string;
  tone?: 'neutral' | 'accent';
}) {
  const [draft, setDraft] = useState('');

  const add = () => {
    const v = draft.trim();
    if (v && !tags.includes(v)) onChange([...tags, v]);
    setDraft('');
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      add();
    } else if (e.key === 'Backspace' && draft === '' && tags.length > 0) {
      onChange(tags.slice(0, -1));
    }
  };

  return (
    <div className="rounded-sm border border-border bg-surface-sunken p-2">
      <div className="flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <span
            key={tag}
            className={
              tone === 'accent'
                ? 'inline-flex items-center gap-1 rounded-xs border border-transparent bg-accent-subtle px-1.5 py-0.5 text-xs text-accent'
                : 'inline-flex items-center gap-1 rounded-xs border border-border bg-surface-warm px-1.5 py-0.5 text-xs text-fg-2'
            }
          >
            {tag}
            <button
              type="button"
              aria-label={`移除 ${tag}`}
              onClick={() => onChange(tags.filter((t) => t !== tag))}
              className="grid size-3.5 place-items-center rounded-xs text-muted hover:text-fg"
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
          onBlur={add}
          placeholder={tags.length === 0 ? placeholder : '继续添加…'}
          aria-label={ariaLabel}
          className="min-w-[10ch] flex-1 bg-transparent px-1 py-0.5 text-sm text-fg outline-none placeholder:text-muted"
        />
      </div>
    </div>
  );
}
