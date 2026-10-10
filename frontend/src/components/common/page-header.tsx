import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  /** 页面标题 */
  title: string;
  /** 一句话说明这个页面能做什么 */
  description?: string;
  /** 右侧操作区 */
  actions?: ReactNode;
  /** 标题下方的元信息（Token 计数 / 保存状态 / 绑定关系） */
  meta?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, actions, meta, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        'flex flex-col gap-3 border-b border-border-soft px-6 py-4 md:flex-row md:items-start md:justify-between',
        className,
      )}
    >
      <div className="min-w-0 space-y-1">
        <h1 className="title-page text-fg">{title}</h1>
        {description ? (
          <p className="max-w-[72ch] text-base leading-relaxed text-muted">{description}</p>
        ) : null}
        {meta ? <div className="flex flex-wrap items-center gap-3 pt-0.5">{meta}</div> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/** 区块标题：用于内容库分区（"角色卡" / "世界书" / "预设"） */
export function SectionHeading({
  title,
  count,
  hint,
  actions,
  className,
}: {
  title: string;
  count?: number;
  hint?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center justify-between gap-3 pb-3', className)}>
      <div className="flex items-baseline gap-2">
        <h2 className="title-section text-fg">{title}</h2>
        {typeof count === 'number' ? (
          <span className="tech-meta">{count}</span>
        ) : null}
        {hint ? <span className="text-sm text-meta">{hint}</span> : null}
      </div>
      {actions}
    </div>
  );
}
