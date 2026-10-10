import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

/* 状态徽标：语义色走 Token；状态徽标一律"颜色 + 文字"，禁止仅靠颜色表达 */
const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-xs border px-1.5 py-0.5 text-xs font-medium leading-none whitespace-nowrap [&_svg]:size-3',
  {
    variants: {
      variant: {
        neutral: 'border-border bg-surface-warm text-fg-2',
        accent: 'border-transparent bg-accent-subtle text-accent',
        success: 'border-transparent bg-success-subtle text-success',
        warn: 'border-transparent bg-warn-subtle text-warn',
        danger: 'border-transparent bg-danger-subtle text-danger',
        info: 'border-transparent bg-surface-warm text-info',
        outline: 'border-border-strong bg-transparent text-muted',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
