import { cn } from '@/lib/utils';
import { Separator } from '@/components/ui/separator';
import { CircleCheck } from '@/components/icons';
import { STEPS } from './constants';

/** 顶部三步指示（可点切换） */
export function StepIndicator({ step, onSelect }: { step: number; onSelect: (id: number) => void }) {
  return (
    <ol className="flex flex-col gap-1 px-6 py-4 md:flex-row md:items-center md:gap-3">
      {STEPS.map((s, i) => {
        const active = step === s.id;
        const done = step > s.id;
        return (
          <li key={s.id} className="flex min-w-0 flex-1 items-center gap-3">
            <button
              type="button"
              onClick={() => onSelect(s.id)}
              aria-current={active ? 'step' : undefined}
              className={cn(
                'flex min-w-0 flex-1 items-center gap-2.5 rounded-md border px-3 py-2 text-left motion-fast',
                active ? 'border-border-strong bg-surface' : 'border-transparent hover:border-border hover:bg-surface-warm',
              )}
            >
              <span
                className={cn(
                  'grid size-5 shrink-0 place-items-center rounded-full border font-mono text-xs tabular-nums',
                  done
                    ? 'border-transparent bg-success-subtle text-success'
                    : active
                      ? 'border-transparent bg-accent-subtle text-accent'
                      : 'border-border text-meta',
                )}
              >
                {done ? <CircleCheck className="size-3.5" aria-hidden="true" /> : s.id}
              </span>
              <span className="min-w-0">
                <span className={cn('block truncate text-sm font-medium', active ? 'text-fg' : 'text-fg-2')}>
                  {s.title}
                </span>
                <span className="block truncate text-xs text-meta">{s.desc}</span>
              </span>
            </button>
            {i < STEPS.length - 1 ? <Separator orientation="vertical" className="hidden h-8 md:block" /> : null}
          </li>
        );
      })}
    </ol>
  );
}
