import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import type { IconComponent } from '@/components/icons';

interface EmptyStateProps {
  icon: IconComponent;
  /** 一句话说明"现在为什么是空的" */
  title: string;
  /** 具体、可执行的下一步说明——禁止空洞占位文案 */
  description: string;
  /** 主操作（1 个）+ 次操作，真实可用 */
  actions?: ReactNode;
  /** 附加引导（示例入口 / 快捷键提示 / 命令） */
  hint?: ReactNode;
  className?: string;
  /** compact = 用于面板内嵌；default = 用于整页 */
  size?: 'default' | 'compact';
}

/**
 * 空状态（AC-16 强制覆盖点）。
 * 规则：无角色 / 无会话 / 无图集 / 未连后端，一律给引导与示例，不得出现空白页。
 * 文案要求：写"能直接照做"的动作，不写"暂无数据"这类空洞占位。
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  actions,
  hint,
  className,
  size = 'default',
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center text-center',
        size === 'default' ? 'gap-4 py-16' : 'gap-3 py-8',
        className,
      )}
    >
      <div className="empty-mark">
        <Icon className="size-6" aria-hidden="true" />
      </div>
      <div className="max-w-[46ch] space-y-1.5">
        <h2 className={cn('font-medium tracking-tight text-fg', size === 'default' ? 'text-lg' : 'text-md')}>
          {title}
        </h2>
        <p className="text-base leading-relaxed text-muted">{description}</p>
      </div>
      {actions ? <div className="flex flex-wrap items-center justify-center gap-2">{actions}</div> : null}
      {hint ? <div className="mt-1 text-sm text-meta">{hint}</div> : null}
    </div>
  );
}

/** 未连后端 / 请求失败时的统一下沉状态（也覆盖 AC-16 的"未连后端"分支） */
export function ErrorState({
  title = '连不上后端实例',
  description,
  actions,
  className,
}: {
  title?: string;
  description: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-center gap-4 py-14 text-center', className)}>
      <div className="max-w-[52ch] space-y-1.5">
        <h2 className="text-md font-medium tracking-tight text-fg">{title}</h2>
        <p className="text-base leading-relaxed text-muted">{description}</p>
      </div>
      {actions ? <div className="flex flex-wrap items-center justify-center gap-2">{actions}</div> : null}
    </div>
  );
}
