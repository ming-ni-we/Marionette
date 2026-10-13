import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import { EmptyState } from '@/components/common/empty-state';
import { UsersRound, Terminal, TriangleAlert, Network, BookMarked, CircleCheck } from '@/components/icons';
import { tensionLabel } from '@/hooks/use-speakers';
import type { CastMember, SseDirectorEvent, StorySnapshot } from '@/api/types';

/**
 * 导演透明性面板 —— 把 AI 的编排从黑盒变成可解释。
 * -----------------------------------------------------------------------------
 * 这是本产品对「多角色 AI 剧情」这件事最硬的差异化：玩家不仅看到角色轮流说话，
 * 还能打开抽屉看到**导演这一轮为什么这么排**（`reason`）、打算让谁上（`speakers`）、
 * 动了哪些状态（`relation_updates` / `flags`），以及**这一轮是不是降级跑的**。
 *
 * `degraded === true` 必须显著标注——否则用户只会觉得「这次质量怎么突然差了」，
 * 而不知道是模型没吐出合法 JSON、系统退回兜底链路。说清楚比藏起来好。
 */
interface DirectorPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  decision: SseDirectorEvent | null;
  snapshot?: StorySnapshot | null;
  /** 本轮出场角色（合并 cast 后的身份，含色调） */
  cast?: CastMember[];
  className?: string;
}

export function DirectorPanel({
  open,
  onOpenChange,
  decision,
  snapshot,
  cast,
  className,
}: DirectorPanelProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby="director-panel-desc" className={cn('gap-3', className)}>
        <div className="pr-6">
          <SheetTitle>导演在想什么</SheetTitle>
          <SheetDescription id="director-panel-desc" className="mt-1">
            本轮由谁出场、为什么这样安排、动了哪些状态——都是导演的原始裁决。
          </SheetDescription>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          {!decision ? (
            <EmptyState
              size="compact"
              icon={Terminal}
              title="还没有导演裁决"
              description="导演在你发出第一条输入之后才开始工作。演过一轮，这里就会显示他为什么这样排。"
            />
          ) : (
            <>
              {/* ---- 降级告警：必须最先被看到 ---- */}
              {decision.degraded ? (
                <div className="flex items-start gap-2 rounded-md border border-border bg-warn-subtle px-3 py-2.5">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-warn">本轮走了降级链路</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-fg-2">
                      模型这一轮没有给出合法的编排 JSON，系统退回了兜底策略（保留场面、由角色自行推进）。
                      内容依然可用，但节奏可能不如正常轮次。连续多次会出现这种情况，建议检查模型后端。
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-xs text-success">
                  <CircleCheck className="size-3.5" aria-hidden="true" />
                  正常链路（导演给出了合法裁决）
                </div>
              )}

              {/* ---- 裁决理由 ---- */}
              <Section icon={Terminal} title="为什么这样安排">
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-fg-2">
                  {decision.reason?.trim() || '（这一轮导演没有给出理由）'}
                </p>
              </Section>

              {/* ---- 出场演员 ---- */}
              {decision.speakers?.length ? (
                <Section icon={UsersRound} title={`本轮出场 · ${decision.speakers.length} 人`}>
                  <ul className="space-y-2">
                    {decision.speakers.map((s, i) => (
                      <li key={`${s.id}-${i}`} className="rounded-md border border-border-soft bg-surface px-2.5 py-2">
                        <div className="flex items-baseline gap-2">
                          <span className="tech-meta shrink-0">{i + 1}</span>
                          <span className="text-sm font-medium text-fg">{s.name || s.id}</span>
                        </div>
                        {s.intent ? (
                          <p className="mt-1 text-xs leading-relaxed text-fg-2">
                            <span className="text-meta">意图 </span>
                            {s.intent}
                          </p>
                        ) : null}
                        {s.direction ? (
                          <p className="mt-0.5 text-xs leading-relaxed text-meta">
                            <span>表演指示 </span>
                            {s.direction}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </Section>
              ) : null}

              {/* ---- 旁白 ---- */}
              {decision.narration?.trim() ? (
                <Section icon={BookMarked} title="导演写的旁白">
                  <p className="narrative text-sm text-fg-2">{decision.narration}</p>
                </Section>
              ) : null}

              {/* ---- 状态变更 ---- */}
              {decision.relation_updates?.length ? (
                <Section icon={Network} title="关系变化">
                  <ul className="space-y-1.5">
                    {decision.relation_updates.map((r, i) => {
                      const t = tensionLabel(r.tension);
                      const fromName = nameOf(cast, r.from);
                      const toName = nameOf(cast, r.to);
                      return (
                        <li key={`${r.from}-${r.to}-${i}`} className="flex flex-wrap items-center gap-1.5 text-sm">
                          <span className="text-fg-2">
                            {fromName} → {toName}
                          </span>
                          {r.kind ? <Badge variant="neutral">{r.kind}</Badge> : null}
                          <Badge variant={t.variant}>{t.label}</Badge>
                        </li>
                      );
                    })}
                  </ul>
                </Section>
              ) : null}

              {decision.flags && Object.keys(decision.flags).length ? (
                <Section icon={BookMarked} title="剧本旗标">
                  <ul className="space-y-1">
                    {Object.entries(decision.flags).map(([k, v]) => (
                      <li key={k} className="flex items-baseline gap-2 text-xs">
                        <span className="tech-meta shrink-0">{k}</span>
                        <span className="min-w-0 break-all text-fg-2">{String(v)}</span>
                      </li>
                    ))}
                  </ul>
                </Section>
              ) : null}

              {/* ---- 剧情状态快照 ---- */}
              {snapshot ? (
                <Section icon={BookMarked} title="剧情状态">
                  <dl className="space-y-1 text-xs">
                    <Row label="当前幕" value={snapshot.story?.act_id} />
                    <Row label="当前节点" value={snapshot.story?.node_id} />
                    <Row label="轮次" value={snapshot.story?.turn} />
                    <Row label="已触发节点" value={(snapshot.story?.fired_node_ids ?? []).join('、')} />
                    <Row
                      label="待触发"
                      value={
                        snapshot.story?.pending_node
                          ? String(snapshot.story.pending_node.title ?? snapshot.story.pending_node.id)
                          : undefined
                      }
                    />
                    <Row label="导演失败计数" value={snapshot.story?.director_failures} />
                  </dl>
                </Section>
              ) : null}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Terminal;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-border-soft bg-surface-sunken px-3 py-2.5">
      <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-medium tracking-wider text-muted">
        <Icon className="size-3.5" aria-hidden="true" />
        {title}
      </h3>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  if (value === undefined || value === null || value === '') return null;
  return (
    <div className="flex items-baseline gap-2">
      <dt className="shrink-0 text-meta">{label}</dt>
      <dd className="min-w-0 break-all text-fg-2">{String(value)}</dd>
    </div>
  );
}

function nameOf(cast: CastMember[] | undefined, id: string): string {
  return cast?.find((c) => c.id === id)?.name || id;
}

/** 顶部提示条：把「导演已介入」这件事在非侵入位置点明（点击打开面板）。 */
export function DirectorCue({
  decision,
  onOpen,
}: {
  decision: SseDirectorEvent | null;
  onOpen: () => void;
}) {
  if (!decision) return null;
  return (
    <Button variant="ghost" size="sm" onClick={onOpen} className="shrink-0">
      <Terminal className="size-4" aria-hidden="true" />
      导演
      {decision.degraded ? <Badge variant="warn">降级</Badge> : null}
    </Button>
  );
}
