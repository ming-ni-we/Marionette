import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Switch } from '@/components/ui/switch';
import type { IconComponent } from '@/components/icons';

/** 设置页分组外壳：图标 + 标题 + 右侧状态位 + 内容（避免每个分组重复同样的头部结构） */
export function SettingsSection({
  icon: Icon,
  title,
  aside,
  children,
}: {
  icon: IconComponent;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border-soft px-5 py-3.5">
        <Icon className="size-4 text-muted" aria-hidden="true" />
        <h2 className="title-section text-fg">{title}</h2>
        {aside ? <span className="ml-auto">{aside}</span> : null}
      </div>
      <div className="space-y-4 p-5">{children}</div>
    </section>
  );
}

/** 单个开关控件行：标签 + 人话说明 + Switch（设置页 4 控件的原子） */
export function ControlRow({
  label,
  hint,
  checked,
  onCheckedChange,
  disabled,
  boxed,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  disabled?: boolean;
  boxed?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-4 px-4 py-3',
        boxed && 'rounded-md border border-border',
      )}
    >
      <div className="min-w-0">
        <p className={cn('text-base font-medium', disabled ? 'text-meta' : 'text-fg')}>{label}</p>
        <p className="mt-0.5 text-sm leading-relaxed text-muted">{hint}</p>
      </div>
      <Switch
        checked={checked}
        onCheckedChange={onCheckedChange}
        label={label}
        disabled={disabled}
        className="mt-0.5"
      />
    </div>
  );
}
