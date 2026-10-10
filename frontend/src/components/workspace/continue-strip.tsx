import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Clock, UserRound, MessageSquare } from '@/components/icons';

export interface ContinueItem {
  id: string;
  kind: 'card' | 'session';
  title: string;
  subtitle: string;
  to: string;
}

/** 「继续上次」横向带：最近会话 + 最近编辑的卡（docs/03-uiux.md §7.1） */
export function ContinueStrip({ items, className }: { items: ContinueItem[]; className?: string }) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="continue-title" className={cn('space-y-2', className)}>
      <h2 id="continue-title" className="flex items-center gap-1.5 label-caps">
        <Clock className="size-3.5" aria-hidden="true" />
        继续上次
      </h2>
      <ul className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {items.map((item) => (
          <li key={`${item.kind}-${item.id}`} className="shrink-0">
            <Link
              to={item.to}
              className="flex w-60 items-start gap-2.5 rounded-md border border-border bg-surface px-3 py-2.5 motion-fast hover:border-border-strong hover:bg-surface-raised"
            >
              <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-sm border border-border bg-surface-warm text-muted">
                {item.kind === 'card' ? (
                  <UserRound className="size-4" aria-hidden="true" />
                ) : (
                  <MessageSquare className="size-4" aria-hidden="true" />
                )}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-base font-medium text-fg">{item.title}</span>
                <span className="mt-0.5 block truncate text-xs text-muted">{item.subtitle}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
