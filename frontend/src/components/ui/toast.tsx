import * as React from 'react';
import * as ToastPrimitive from '@radix-ui/react-toast';
import { cn } from '@/lib/utils';
import { useToastStore, type ToastItem } from '@/stores/ui';
import { CircleCheck, CircleAlert, TriangleAlert, Info, X } from '@/components/icons';

const VARIANT_META: Record<
  ToastItem['variant'],
  { icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>; tone: string }
> = {
  default: { icon: Info, tone: 'text-info' },
  success: { icon: CircleCheck, tone: 'text-success' },
  warn: { icon: TriangleAlert, tone: 'text-warn' },
  danger: { icon: CircleAlert, tone: 'text-danger' },
};

const DURATION = 4200;

function ToastRow({ item }: { item: ToastItem }) {
  const dismiss = useToastStore((s) => s.dismiss);
  const meta = VARIANT_META[item.variant];
  const Icon = meta.icon;
  return (
    <ToastPrimitive.Root
      open
      duration={DURATION}
      onOpenChange={(open) => {
        if (!open) dismiss(item.id);
      }}
      className={cn(
        'flex items-start gap-3 rounded-md border border-border bg-surface-raised p-3 animate-fade-in-up',
        'data-[state=closed]:opacity-0',
      )}
    >
      <Icon className={cn('size-4 shrink-0 mt-0.5', meta.tone)} aria-hidden />
      <div className="flex-1 min-w-0">
        <ToastPrimitive.Title className="text-base font-medium text-fg">
          {item.title}
        </ToastPrimitive.Title>
        {item.description ? (
          <ToastPrimitive.Description className="mt-0.5 text-sm leading-relaxed text-muted">
            {item.description}
          </ToastPrimitive.Description>
        ) : null}
      </div>
      <ToastPrimitive.Close
        aria-label="关闭通知"
        className="grid size-5 shrink-0 place-items-center rounded-xs text-muted motion-fast hover:bg-surface-warm hover:text-fg"
      >
        <X className="size-3.5" aria-hidden="true" />
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  );
}

/** 全局通知区域：挂在 App 根部，订阅 toast store */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {toasts.map((t) => (
        <ToastRow key={t.id} item={t} />
      ))}
      <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-toast flex w-[360px] max-w-[92vw] flex-col gap-2 outline-none" />
    </ToastPrimitive.Provider>
  );
}
