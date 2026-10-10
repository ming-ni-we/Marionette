import { Link, useNavigate } from 'react-router-dom';
import { relativeTime, truncate } from '@/lib/utils';
import { ioApi } from '@/api/client';
import type { Card, Preset, Session, WorldBook } from '@/api/types';
import { SectionHeading } from '@/components/common/page-header';
import { DataCard } from '@/components/common/data-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  UserRound,
  BookOpen,
  SlidersHorizontal,
  MessageSquare,
  Ellipsis,
  CirclePlus,
  Trash2,
  FileDown,
  Pencil,
} from '@/components/icons';

/** 内容卡网格：固定最小列宽 + 自动填充，超宽屏靠 max-width 收敛而非拉伸单列 */
const GRID =
  'grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-2.5 max-w-[--container-max]';

/** 空分组提示行（虚线框 + 可执行下一步） */
export function SectionHint({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border px-4 py-6">
      <p className="text-sm leading-relaxed text-muted">{children}</p>
    </div>
  );
}

export function CardSection({
  items,
  query,
  offline,
  onRemove,
}: {
  items: Card[];
  query: string;
  offline: boolean;
  onRemove: (id: string) => void;
}) {
  const navigate = useNavigate();
  return (
    <section aria-labelledby="sec-cards">
      <SectionHeading
        title="角色卡"
        count={items.length}
        hint="点开卡可以编辑人设，或直接开会话"
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link to="/cards/new">
              <CirclePlus className="size-4" aria-hidden="true" />
              新建
            </Link>
          </Button>
        }
      />
      {items.length === 0 ? (
        <SectionHint>
          这个筛选下没有角色卡。清掉筛选，或者
          <Link to="/cards/new" className="mx-1 text-accent underline underline-offset-2">
            新建一张
          </Link>
          。
        </SectionHint>
      ) : (
        <ul className={GRID}>
          {items.map((card) => (
            <li key={card.id}>
              <DataCard
                icon={UserRound}
                tone="accent"
                title={card.data.name}
                description={truncate(card.data.description.replace(/\s+/g, ' '), 96)}
                tags={card.data.tags}
                highlightQuery={query}
                onOpen={() => navigate(`/cards/${card.id}`)}
                meta={
                  <>
                    <span>{relativeTime(card.updated_at)}</span>
                    <span className="font-mono tabular-nums">{card.data.first_mes.length} 字开场白</span>
                    <button
                      type="button"
                      className="ml-auto rounded-xs text-muted motion-fast hover:text-accent focus-visible:text-accent group-hover/card:text-accent group-focus-within/card:text-accent"
                      onClick={() => navigate(`/sessions?card=${card.id}`)}
                    >
                      开会话
                    </button>
                  </>
                }
                menu={
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon-sm" aria-label={`${card.data.name} 的更多操作`}>
                        <Ellipsis className="size-4" aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => navigate(`/cards/${card.id}`)}>
                        <Pencil className="size-4" aria-hidden="true" />
                        打开编辑器
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => navigate(`/sessions?card=${card.id}`)}>
                        <MessageSquare className="size-4" aria-hidden="true" />
                        开一场会话
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <a href={ioApi.exportCardUrl(card.id)} download>
                          <FileDown className="size-4" aria-hidden="true" />
                          导出为 Tavern V2
                        </a>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        destructive
                        disabled={offline}
                        onSelect={() => {
                          if (window.confirm(`删除「${card.data.name}」？绑定的世界书不会一起删。`)) {
                            onRemove(card.id);
                          }
                        }}
                      >
                        <Trash2 className="size-4" aria-hidden="true" />
                        删除角色卡
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                }
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function WorldBookSection({ items, query }: { items: WorldBook[]; query: string }) {
  const navigate = useNavigate();
  return (
    <section aria-labelledby="sec-worldbooks">
      <SectionHeading
        title="世界书"
        count={items.length}
        hint="关键词触发的设定，一卡可绑多本"
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link to="/worldbooks/new">
              <CirclePlus className="size-4" aria-hidden="true" />
              新建
            </Link>
          </Button>
        }
      />
      {items.length === 0 ? (
        <SectionHint>
          还没有世界书。世界书用来装「角色不会主动说，但一旦被提到就必须对得上」的设定 ——
          比如地标、旧物件、街坊的名字。
        </SectionHint>
      ) : (
        <ul className={GRID}>
          {items.map((wb) => (
            <li key={wb.id}>
              <DataCard
                icon={BookOpen}
                title={wb.data.name || '未命名世界书'}
                description={truncate(wb.data.description || '还没有描述。', 96)}
                highlightQuery={query}
                onOpen={() => navigate(`/worldbooks/${wb.id}`)}
                meta={
                  <>
                    <span className="font-mono tabular-nums">{wb.data.entries.length} 条条目</span>
                    <span className="font-mono tabular-nums">预算 {wb.data.token_budget}</span>
                    <span>{relativeTime(wb.updated_at)}</span>
                  </>
                }
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function PresetSection({ items, query }: { items: Preset[]; query: string }) {
  const navigate = useNavigate();
  return (
    <section aria-labelledby="sec-presets">
      <SectionHeading
        title="预设"
        count={items.length}
        hint="系统提示词与采样参数"
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link to="/presets/new">
              <CirclePlus className="size-4" aria-hidden="true" />
              新建
            </Link>
          </Button>
        }
      />
      {items.length === 0 ? (
        <SectionHint>
          还没有预设。预设决定模型的说话方式与上下文预算分配 —— 开会话时会自动挑一套默认预设。
        </SectionHint>
      ) : (
        <ul className={GRID}>
          {items.map((p) => (
            <li key={p.id}>
              <DataCard
                icon={SlidersHorizontal}
                title={p.data.name || '未命名预设'}
                description={truncate(p.data.description || '还没有描述。', 96)}
                highlightQuery={query}
                onOpen={() => navigate(`/presets/${p.id}`)}
                meta={
                  <>
                    <span className="font-mono tabular-nums">temp {p.data.sampling.temperature}</span>
                    <span className="font-mono tabular-nums">
                      {p.data.context_budget.max_context_tokens} ctx
                    </span>
                    <span>{relativeTime(p.updated_at)}</span>
                  </>
                }
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function SessionSection({ items }: { items: Session[] }) {
  return (
    <section aria-labelledby="sec-sessions">
      <SectionHeading
        title="会话"
        count={items.length}
        hint="继续上次，或从任意一张卡开新的"
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link to="/sessions">查看全部</Link>
          </Button>
        }
      />
      {items.length === 0 ? (
        <SectionHint>
          还没有会话。在上面挑一张角色卡，点「开会话」—— 第一次会话会自动用示例世界书与默认预设。
        </SectionHint>
      ) : (
        <ul className="divide-y divide-border-soft rounded-lg border border-border bg-surface">
          {items.slice(0, 5).map((s) => (
            <li key={s.id}>
              <Link
                to={`/sessions/${s.id}`}
                className="flex items-center gap-3 px-3 py-2.5 motion-fast hover:bg-surface-warm"
              >
                <MessageSquare className="size-4 shrink-0 text-muted" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-base text-fg">{s.scene.summary || '未命名会话'}</span>
                  <span className="mt-0.5 block truncate text-xs text-meta">
                    {s.scene.location} · {s.scene.time}
                  </span>
                </span>
                <Badge variant={s.status === 'active' ? 'success' : 'neutral'}>
                  {s.status === 'active' ? '进行中' : s.status === 'paused' ? '已暂停' : '已归档'}
                </Badge>
                <span className="tech-meta shrink-0">{s.state_machine.turn} 轮</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
