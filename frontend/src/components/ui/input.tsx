import * as React from 'react';
import { cn } from '@/lib/utils';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type = 'text', ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        'flex h-[var(--density-control-height)] w-full rounded-sm border border-border bg-surface-sunken px-3 text-base text-fg',
        'placeholder:text-muted',
        'motion-fast hover:border-border-strong',
        'focus-visible:border-accent focus-visible:bg-surface',
        'disabled:cursor-not-allowed disabled:opacity-45',
        'file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-fg-2',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
