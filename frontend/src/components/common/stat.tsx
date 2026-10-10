import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import type { IconComponent } from '@/components/icons';

/** 指标块：数字用等宽 + tabular-nums，变化时不重排 */
export function StatTile({
  label,
  value,
  icon: Icon,
  tone = 'neutral',
  hint,
  className,
}: {
  label: string;
  value: ReactNode;
  icon?: IconComponent;
  tone?: 'neutral' | 'accent' | 'success' | 'warn' | 'danger' | 'info';
  hint?: string;
  className?: string;
}) {
  const toneClass: Record<NonNullable<typeof tone>, string> = {
    neutral: 'text-fg-2',
    accent: 'text-accent',
    success: 'text-success',
    warn: 'text-warn',
    danger: 'text-danger',
    info: 'text-info',
  };
  return (
    <div className={cn('rounded-md border border-border bg-surface px-3 py-2.5', className)}>
      <div className="flex items-center gap-1.5 text-muted">
        {Icon ? <Icon className="size-3.5" aria-hidden="true" /> : null}
        <span className="label-caps">{label}</span>
      </div>
      <div className={cn('mt-1 font-mono text-xl tabular-nums', toneClass[tone])}>{value}</div>
      {hint ? <div className="mt-0.5 text-xs text-meta">{hint}</div> : null}
    </div>
  );
}
