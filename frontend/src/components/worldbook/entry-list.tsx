import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { ScrollArea } from '@/components/ui/scroll-area';
import { EmptyState } from '@/components/common/empty-state';
import { CirclePlus, KeyRound } from '@/components/icons';
import type { WorldBookEntry } from '@/api/types';

/** 世界书条目左侧列表（选择 · 启用开关 · 新增 · 空状态）。 */
export function EntryList({
  entries,
  selected,
  onSelect,
  onToggle,
  onAdd,
}: {
  entries: WorldBookEntry[];
  selected: number;
  onSelect: (i: number) => void;
  onToggle: (i: number, enabled: boolean) => void;
  onAdd: () => void;
}) {
  return (
    <nav aria-label="世界书条目" className="border-r border-border">
      <div className="flex items-center justify-between gap-2 border-b border-border-soft px-3 py-2.5">
        <span className="label-caps">条目列表</span>
        <Button variant="ghost" size="icon-sm" aria-label="新增条目" onClick={onAdd}>
          <CirclePlus className="size-4" aria-hidden="true" />
        </Button>
      </div>

      {entries.length === 0 ? (
        <div className="px-3 py-4">
          <EmptyState
            size="compact"
            icon={KeyRound}
            title="还没有条目"
            description="一条条目 = 一个「被提到就该生效」的设定。比如地标、旧物件、街坊的名字。"
            actions={
              <Button variant="secondary" size="sm" onClick={onAdd}>
                <CirclePlus className="size-4" aria-hidden="true" />
                添加第一条
              </Button>
            }
          />
        </div>
      ) : (
        <ScrollArea className="max-h-[calc(100dvh-9rem)]">
          <ul className="space-y-0.5 p-2">
            {entries.map((entry, i) => (
              <li key={i}>
                <div
                  className={cn(
                    'rounded-md border px-2.5 py-2 motion-fast',
                    i === selected
                      ? 'border-border-strong bg-surface-warm'
                      : 'border-transparent hover:border-border hover:bg-surface-warm',
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <button
                        type="button"
                        onClick={() => onSelect(i)}
                        className="block w-full text-left"
                        aria-current={i === selected ? 'true' : undefined}
                      >
                        <span
                          className={cn(
                            'block truncate text-base',
                            entry.enabled ? 'text-fg' : 'text-muted line-through',
                          )}
                        >
                          {entry.comment || entry.keys.join(' / ') || `条目 ${i + 1}`}
                        </span>
                        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-meta">
                          {entry.constant ? (
                            <span className="text-accent">常驻</span>
                          ) : entry.keys.length > 0 ? (
                            <span className="truncate">
                              关键词 {entry.keys.slice(0, 3).join('、')}
                            </span>
                          ) : (
                            <span className="text-warn">未设触发条件</span>
                          )}
                          <span className="font-mono tabular-nums">P{entry.priority}</span>
                        </span>
                      </button>
                    </div>
                    <Switch
                      checked={entry.enabled}
                      onCheckedChange={(v) => onToggle(i, v)}
                      label={`启用条目 ${entry.comment || i + 1}`}
                      className="mt-0.5"
                    />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </ScrollArea>
      )}
    </nav>
  );
}
