import * as React from 'react';
import { cn } from '@/lib/utils';

/* 骨架屏：低频脉动（reduced-motion 下由 tokens.css 全局规则降速为静止） */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-sm bg-surface-warm', className)}
      {...props}
    />
  );
}
