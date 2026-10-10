import * as React from 'react';
import { cn } from '@/lib/utils';

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'flex min-h-20 w-full resize-y rounded-sm border border-border bg-surface-sunken px-3 py-2 text-base leading-relaxed text-fg',
      'placeholder:text-muted',
      'motion-fast hover:border-border-strong',
      'focus-visible:border-accent focus-visible:bg-surface',
      'disabled:cursor-not-allowed disabled:opacity-45',
      className,
    )}
    {...props}
  />
));
Textarea.displayName = 'Textarea';
