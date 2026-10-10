import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { LoaderCircle } from '@/components/icons';

/* 按钮：6 态齐备 —— Default / Hover / Focus / Active / Disabled / Loading
 * 焦点环由 tokens.css 的全局 :focus-visible 提供（禁止自定义发光环）
 * 高度对齐 --density-control-height（studio 32px / session 36px） */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm font-medium motion-fast select-none disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-accent-on hover:bg-accent-hover active:bg-accent-active',
        secondary:
          'bg-surface-warm text-fg border border-border hover:border-border-strong hover:bg-surface-raised active:bg-surface-raised',
        outline:
          'border border-border bg-transparent text-fg-2 hover:bg-surface-warm hover:text-fg active:bg-surface-raised',
        ghost: 'bg-transparent text-fg-2 hover:bg-surface-warm hover:text-fg active:bg-surface-raised',
        danger: 'bg-danger text-white hover:opacity-90 active:opacity-80',
        link: 'bg-transparent text-accent underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-7 px-2.5 text-sm',
        default: 'h-[var(--density-control-height)] px-3 text-base',
        lg: 'h-9 px-4 text-md',
        icon: 'size-[var(--density-control-height)]',
        'icon-sm': 'size-7',
      },
    },
    defaultVariants: { variant: 'secondary', size: 'default' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, disabled, children, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading ? (
          <>
            <LoaderCircle className="size-4 animate-spin-slow" aria-hidden="true" />
            {children}
          </>
        ) : (
          children
        )}
      </Comp>
    );
  },
);
Button.displayName = 'Button';

export { buttonVariants };
