import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface FieldProps {
  label: string;
  /** 关联控件的 id，保证 label 点击聚焦 */
  htmlFor?: string;
  /** 人话化的字段说明（直接修正"术语暴露"病灶） */
  hint?: string;
  /** 可选字段用"可选"标签，而不是红色错误 */
  optional?: boolean;
  error?: string;
  children: ReactNode;
  className?: string;
  /** 右侧辅助（Token 数 / 字符数） */
  accessory?: ReactNode;
}

export function Field({
  label,
  htmlFor,
  hint,
  optional,
  error,
  children,
  className,
  accessory,
}: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="text-sm font-medium text-fg-2">
          {label}
          {optional ? <span className="ml-1.5 text-xs font-normal text-meta">可选</span> : null}
        </label>
        {accessory}
      </div>
      {children}
      {hint && !error ? (
        <p className="text-sm leading-relaxed text-meta">{hint}</p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm leading-relaxed text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
