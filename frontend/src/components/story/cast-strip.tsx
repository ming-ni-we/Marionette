import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Hint } from '@/components/ui/tooltip';
import { UsersRound } from '@/components/icons';
import type { SpeakerIndex } from '@/hooks/use-speakers';

/**
 * 在场角色条。
 * -----------------------------------------------------------------------------
 * 剧情模式一轮有多人开口，读者需要一个「现在台上有谁」的常驻参照。
 * 当前正在说话的人（`activeSpeakerId`）会在条上高亮 —— 这样即使正文滚到上面去了，
 * 读者也能一眼确认「现在是林禾在说」。
 *
 * 头像位用的是与气泡完全相同的 `toneClass`（来自 `useSpeakers`），
 * 保证「条上的色块」和「气泡的色块」是同一个人。
 */
export function CastStrip({
  speakers,
  activeSpeakerId,
  className,
}: {
  speakers: SpeakerIndex;
  activeSpeakerId?: string | null;
  className?: string;
}) {
  const present = speakers.present;
  if (present.length === 0) return null;

  return (
    <div
      className={cn(
        'border-b border-border-soft bg-surface px-4 py-2',
        className,
      )}
      aria-label="在场角色"
    >
      <div className="mx-auto flex w-full max-w-[68ch] flex-wrap items-center gap-x-2 gap-y-1.5">
        <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-muted">
          <UsersRound className="size-3.5" aria-hidden="true" />
          在场
        </span>

        {present.map((s) => {
          const active = activeSpeakerId === s.id;
          return (
            <Hint key={s.id} label={active ? `${s.name}（正在说话）` : s.name}>
              <span
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 motion-fast',
                  s.toneClass,
                  active ? 'ring-1 ring-accent/50' : 'opacity-80',
                )}
              >
                <span
                  aria-hidden="true"
                  className="grid size-4 place-items-center rounded-xs text-[10px] font-medium"
                >
                  {s.initial}
                </span>
                <span className="text-xs font-medium">{s.name}</span>
              </span>
            </Hint>
          );
        })}

        {activeSpeakerId ? (
          <Badge variant="accent" className="shrink-0">
            正在说话
          </Badge>
        ) : null}
      </div>
    </div>
  );
}
