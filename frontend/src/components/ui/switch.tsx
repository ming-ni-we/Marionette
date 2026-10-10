import * as React from 'react';
import { cn } from '@/lib/utils';

/* 开关：世界书条目启用 / 审核层开关等
 * 语义色走 Token；配 aria-checked，键盘可达（Space / Enter） */
export interface SwitchProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onChange' | 'role'> {
  checked: boolean;
  onCheckedChange?: (checked: boolean) => void;
  label: string;
}

export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked, onCheckedChange, label, className, disabled, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border motion-fast',
        'focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-45',
        checked ? 'border-transparent bg-accent' : 'border-border bg-surface-sunken',
        className,
      )}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none block size-3.5 rounded-full bg-surface transition-transform duration-[var(--dur-fast)] ease-[var(--ease-standard)]',
          checked ? 'translate-x-[18px]' : 'translate-x-[3px]',
        )}
      />
    </button>
  ),
);
Switch.displayName = 'Switch';
