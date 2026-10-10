import { useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown, CircleHelp } from '@/components/icons';

interface GroupSectionProps {
  id: string;
  title: string;
  /** 分组用途说明——用文字表达语义，不用颜色分区（直接修正酒馆的绿蓝红病灶） */
  description?: string;
  defaultOpen?: boolean;
  /** 折叠时的摘要（如"3 个字段已填"） */
  summary?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** 可折叠分组：渐进披露的载体（常用区默认展开，高级区默认折叠） */
export function GroupSection({
  id,
  title,
  description,
  defaultOpen = true,
  summary,
  children,
  className,
}: GroupSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = `${id}-content`;
  return (
    <section className={cn('border-b border-border-soft last:border-b-0', className)}>
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-2 py-3 text-left motion-fast hover:text-fg"
        >
          <ChevronDown
            className={cn('size-4 shrink-0 text-muted motion-fast', open && 'rotate-180')}
            aria-hidden="true"
          />
          <span className="text-md font-medium tracking-tight text-fg">{title}</span>
          {summary ? <span className="ml-auto text-sm text-meta">{summary}</span> : null}
        </button>
      </h3>
      {open ? (
        <div id={contentId} className="space-y-4 pb-5 pl-6 pr-1">
          {description ? (
            <p className="flex items-start gap-1.5 text-sm leading-relaxed text-muted">
              <CircleHelp className="mt-0.5 size-3.5 shrink-0 text-meta" aria-hidden="true" />
              <span>{description}</span>
            </p>
          ) : null}
          {children}
        </div>
      ) : null}
    </section>
  );
}

/** 左栏字段导航：锚点目录（角色卡编辑器左侧） */
export function NavList({
  items,
  activeId,
  onSelect,
  className,
}: {
  items: Array<{ id: string; label: string; hint?: string }>;
  activeId?: string;
  onSelect: (id: string) => void;
  className?: string;
}) {
  return (
    <nav aria-label="字段分组导航" className={cn('space-y-0.5', className)}>
      {items.map((item) => {
        const active = item.id === activeId;
        return (
          <button
            key={item.id}
            type="button"
            aria-current={active ? 'true' : undefined}
            onClick={() => onSelect(item.id)}
            className={cn(
              'block w-full rounded-sm px-2.5 py-1.5 text-left text-base motion-fast',
              active
                ? 'bg-accent-subtle text-accent'
                : 'text-fg-2 hover:bg-surface-warm hover:text-fg',
            )}
          >
            <span className="block truncate">{item.label}</span>
            {item.hint ? (
              <span className="mt-0.5 block truncate text-xs text-meta">{item.hint}</span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
