import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { X } from '@/components/icons';

/* Sheet = 边缘抽屉（右侧元信息抽屉 / 分支树用）
 * overlay 形式，不重排阅读列（见 docs/03-uiux.md §7.3） */
export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

const sheetVariants = cva(
  'fixed z-drawer flex flex-col gap-4 bg-surface-raised p-5 border-border',
  {
    variants: {
      side: {
        right: 'inset-y-0 right-0 h-full w-[var(--drawer-width)] max-w-[92vw] border-l animate-drawer-in',
        left: 'inset-y-0 left-0 h-full w-[var(--drawer-width)] max-w-[92vw] border-r animate-fade-in',
      },
    },
    defaultVariants: { side: 'right' },
  },
);

export interface SheetContentProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>,
    VariantProps<typeof sheetVariants> {}

export const SheetContent = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Content>,
  SheetContentProps
>(({ side = 'right', className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-overlay bg-scrim animate-fade-in" />
    <DialogPrimitive.Content ref={ref} className={cn(sheetVariants({ side }), className)} {...props}>
      {children}
      <DialogPrimitive.Close
        aria-label="关闭抽屉"
        className="absolute right-3 top-3 grid size-7 place-items-center rounded-sm text-muted motion-fast hover:bg-surface-warm hover:text-fg"
      >
        <X className="size-4" aria-hidden="true" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = 'SheetContent';

export const SheetTitle = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn('text-md font-semibold tracking-tight text-fg', className)}
    {...props}
  />
));
SheetTitle.displayName = 'SheetTitle';

export const SheetDescription = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm leading-relaxed text-muted', className)}
    {...props}
  />
));
SheetDescription.displayName = 'SheetDescription';
