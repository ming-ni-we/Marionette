import * as React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { cn } from '@/lib/utils';
import { ChevronDown, Check } from '@/components/icons';

export const Select = SelectPrimitive.Root;
export const SelectGroup = SelectPrimitive.Group;
export const SelectValue = SelectPrimitive.Value;

export const SelectTrigger = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      'flex h-[var(--density-control-height)] w-full items-center justify-between gap-2 rounded-sm border border-border bg-surface-sunken px-3 text-base text-fg',
      'motion-fast hover:border-border-strong data-[placeholder]:text-muted',
      'focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-45',
      className,
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="size-4 shrink-0 text-muted" aria-hidden="true" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
));
SelectTrigger.displayName = 'SelectTrigger';

export const SelectContent = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = 'popper', ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      position={position}
      className={cn(
        'relative z-dropdown max-h-80 min-w-[8rem] overflow-hidden rounded-md border border-border bg-surface-raised p-1 animate-fade-in',
        position === 'popper' && 'w-[var(--radix-select-trigger-width)]',
        className,
      )}
      {...props}
    >
      <SelectPrimitive.Viewport>{children}</SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
SelectContent.displayName = 'SelectContent';

export const SelectItem = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex w-full cursor-default select-none items-center gap-2 rounded-sm py-1.5 pl-7 pr-2 text-base text-fg-2 outline-none motion-fast',
      'data-[highlighted]:bg-surface-warm data-[state=checked]:text-fg data-[disabled]:pointer-events-none data-[disabled]:opacity-45',
      className,
    )}
    {...props}
  >
    <span className="absolute left-2 grid size-4 place-items-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="size-4 text-accent" aria-hidden="true" />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = 'SelectItem';

export const SelectLabel = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.Label
    ref={ref}
    className={cn('px-2 py-1 text-xs font-medium tracking-wider text-muted uppercase', className)}
    {...props}
  />
));
SelectLabel.displayName = 'SelectLabel';
