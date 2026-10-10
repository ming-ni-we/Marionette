import type { ReactNode } from 'react';
import { cn, splitHighlight } from '@/lib/utils';
import type { IconComponent } from '@/components/icons';

/** 高亮命中的关键词（前端关键词高亮，见架构 §4.7） */
export function Highlighted({ text, query }: { text: string; query?: string }) {
  const parts = splitHighlight(text, query ?? '');
  return (
    <>
      {parts.map((p, i) =>
        p.hit ? (
          <mark key={i} className="rounded-xs bg-accent-subtle px-0.5 text-accent">
            {p.text}
          </mark>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
}

interface DataCardProps {
  icon: IconComponent;
  title: string;
  description?: string;
  tags?: string[];
  /** 底部元信息（时间 / 条目数 / Token） */
  meta?: ReactNode;
  /** 右上角操作菜单 */
  menu?: ReactNode;
  /** 缩略图位（头像 / 资产预览）；无图时用图标位 */
  thumbnail?: ReactNode;
  onOpen?: () => void;
  highlightQuery?: string;
  /** 语义强调：仅用于图标着色，不做整卡着色（保持中性 70-90%） */
  tone?: 'accent' | 'neutral';
  className?: string;
}

/**
 * 内容库条目卡（角色卡 / 世界书 / 预设 / 会话 / 资产通用）。
 * 1px 描边表达层次，无嵌套卡片，无重阴影。
 */
export function DataCard({
  icon: Icon,
  title,
  description,
  tags = [],
  meta,
  menu,
  thumbnail,
  onOpen,
  highlightQuery,
  tone = 'neutral',
  className,
}: DataCardProps) {
  const interactive = Boolean(onOpen);
  return (
    <div
      className={cn(
        'group/card relative flex flex-col rounded-lg border border-border bg-surface motion-fast',
        interactive && 'hover:border-border-strong hover:bg-surface-raised',
        className,
      )}
    >
      <div className="flex items-start gap-3 p-3">
        {thumbnail ?? (
          <span
            className={cn(
              'grid size-9 shrink-0 place-items-center rounded-md border border-border bg-surface-warm',
              tone === 'accent' ? 'text-accent' : 'text-muted',
            )}
          >
            <Icon className="size-5" aria-hidden="true" />
          </span>
        )}

        <div className="min-w-0 flex-1">
          {interactive ? (
            <button
              type="button"
              onClick={onOpen}
              className="block w-full text-left focus-visible:outline-none"
            >
              <span className="block truncate text-md font-medium text-fg">
                <Highlighted text={title} query={highlightQuery} />
              </span>
            </button>
          ) : (
            <span className="block truncate text-md font-medium text-fg">
              <Highlighted text={title} query={highlightQuery} />
            </span>
          )}
          {description ? (
            <p className="mt-0.5 line-clamp-2 text-sm leading-relaxed text-muted">
              <Highlighted text={description} query={highlightQuery} />
            </p>
          ) : null}
        </div>

        {menu ? <div className="shrink-0">{menu}</div> : null}
      </div>

      {tags.length > 0 ? (
        <div className="flex flex-wrap gap-1 px-3 pb-2">
          {tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="rounded-xs border border-border-soft bg-surface-warm px-1.5 py-0.5 text-xs text-muted"
            >
              {tag}
            </span>
          ))}
          {tags.length > 4 ? (
            <span className="px-1 text-xs text-meta">+{tags.length - 4}</span>
          ) : null}
        </div>
      ) : null}

      {meta ? (
        <div className="mt-auto flex items-center gap-3 border-t border-border-soft px-3 py-2 text-xs text-meta">
          {meta}
        </div>
      ) : null}
    </div>
  );
}
