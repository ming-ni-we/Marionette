import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cn, relativeTime } from '@/lib/utils';
import { sessionsApi, worldsApi } from '@/api/client';
import type { Session, SessionStatus } from '@/api/types';
import { STORY_SPEC, RPG_SPEC } from '@/api/types';
import { SAMPLE_SESSIONS, SAMPLE_WORLDS } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';
import { PageHeader } from '@/components/common/page-header';
import { LibraryToolbar } from '@/components/common/library-toolbar';
import { EmptyState } from '@/components/common/empty-state';
import { OfflineBanner } from '@/components/common/offline-banner';
import { NewSessionDialog } from '@/components/session/new-session-dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  MessageSquare,
  CirclePlus,
  Ellipsis,
  GitFork,
  Trash2,
  Pause,
  Archive,
  GitBranch,
  ArrowRight,
  BookOpen,
  Compass,
} from '@/components/icons';
import { useLibraryController } from '@/hooks/use-library';

const STATUS_LABEL: Record<SessionStatus, string> = {
  active: '进行中',
  paused: '已暂停',
  archived: '已归档',
};

/** `spec` 筛选：全部 / 单人对话 / 剧情。 */
type SpecFilter = 'all' | typeof RPG_SPEC | typeof STORY_SPEC;

/**
 * 剧情会话判定。
 *
 * 依据 `spec` 字段而非 `world_id` —— `spec` 是后端分派 `create_story_session()`
 * 时写入的权威标识。以 `spec` 为准，前端就不会因为后端某天调整 `world_id`
 * 的填充时机而误判。
 *
 * 兜底：老数据若 `spec` 缺失但有 `world_id`，仍按剧情处理——宁可多给一个
 * 标签，也不要让用户点进 `/sessions/:id` 看到剧情会话渲染成 1v1 布局。
 */
export const isStorySession = (s: Pick<Session, 'spec' | 'world_id'>) =>
  s.spec === STORY_SPEC || Boolean(s.world_id);

/** 剧情会话进演出页，单人对话进运行时页。 */
export const sessionHref = (s: Pick<Session, 'id' | 'spec' | 'world_id'>) =>
  isStorySession(s) ? `/stories/${s.id}` : `/sessions/${s.id}`;

export function SessionListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const lib = useLibraryController({ sort: 'last_message_at' });
  const [status, setStatus] = useState<SessionStatus | 'all'>('all');
  const [spec, setSpec] = useState<SpecFilter>('all');
  const [dialogOpen, setDialogOpen] = useState(false);

  // /sessions?card=<id> → 直接打开开会话弹窗（内容库「开会话」入口）
  const cardParam = params.get('card') ?? undefined;
  useEffect(() => {
    if (cardParam) setDialogOpen(true);
  }, [cardParam]);

  const query = useQuery({
    queryKey: ['sessions', lib.searchQuery, status],
    queryFn: () => sessionsApi.list({ ...lib.searchQuery, status: status === 'all' ? undefined : status }),
    retry: false,
  });

  // 世界观名单：给剧情会话补上「在哪个世界」的标题。
  // 后端会话里只有 world_id，没有标题；离线时退回演示世界观。
  const worldsQuery = useQuery({
    queryKey: ['worlds', 'session-list'],
    queryFn: () => worldsApi.list({ limit: 100 }),
    retry: false,
  });

  const offline = query.isError;
  const worlds = worldsQuery.data?.items ?? (worldsQuery.isError ? SAMPLE_WORLDS : []);
  const worldTitle = (id: string | null | undefined) =>
    id ? worlds.find((w) => w.id === id)?.title ?? '' : '';

  const items: Session[] = offline
    ? SAMPLE_SESSIONS.filter((s) => (status === 'all' ? true : s.status === status))
    : query.data?.items ?? [];

  // 剧情筛选在客户端做：后端 `GET /sessions` 目前不支持按 spec 过滤。
  // 会话量级是"人手上的会话"，本地过滤没有性能问题，且避免为它改后端契约。
  const visible = spec === 'all' ? items : items.filter((s) => (spec === STORY_SPEC) === isStorySession(s));

  const remove = useMutation({
    mutationFn: (id: string) => sessionsApi.remove(id),
    onSuccess: () => {
      toast.success('会话已删除');
      void qc.invalidateQueries({ queryKey: ['sessions'] });
    },
    onError: () => toast.danger('删除失败', '后端没有确认这次删除。'),
  });

  const fork = useMutation({
    mutationFn: (sessionId: string) => sessionsApi.fork(sessionId, {}),
    onSuccess: (s) => {
      toast.success('已创建分支会话', '新会话从最后一条消息处接续。');
      void qc.invalidateQueries({ queryKey: ['sessions'] });
      navigate(sessionHref(s));
    },
    onError: () => toast.danger('分支失败', '后端拒绝了这次分叉请求。'),
  });

  // 会话没有标签维度，隐藏标签筛选器与已选 chips
  const isFiltering = Boolean(lib.debouncedQuery) || status !== 'all' || spec !== 'all';

  const storyCount = items.filter(isStorySession).length;
  const rpgCount = items.length - storyCount;

  return (
    <div className="flex min-h-dvh flex-col">
      <PageHeader
        title="会话"
        description="每场会话绑定一张角色卡与一套预设；剧情会话则挂在一份世界观上，由 AI 导演安排多角色同台。两种模式在同一个列表里。"
        actions={
          <Button variant="primary" onClick={() => setDialogOpen(true)}>
            <CirclePlus className="size-4" aria-hidden="true" />
            开新会话
          </Button>
        }
      />

      {offline ? (
        <OfflineBanner>
          下面展示的是内置演示会话，可以点进去看运行时的完整交互。
        </OfflineBanner>
      ) : null}

      <div className="space-y-4 px-6 py-5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[240px] flex-1">
            <LibraryToolbar
              query={lib.query}
              onQueryChange={lib.setQuery}
              selectedTags={[]}
              onSelectedTagsChange={() => undefined}
              availableTags={[]}
              showTagFilter={false}
              sort={lib.sort}
              onSortChange={lib.setSort}
              order={lib.order}
              onOrderChange={lib.setOrder}
              sortFields={['last_message_at', 'updated_at', 'created_at']}
              placeholder="搜索会话的标题或场景描述"
            />
          </div>
          <Select value={status} onValueChange={(v) => setStatus(v as SessionStatus | 'all')}>
            <SelectTrigger aria-label="按状态筛选" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="active">进行中</SelectItem>
              <SelectItem value="paused">已暂停</SelectItem>
              <SelectItem value="archived">已归档</SelectItem>
            </SelectContent>
          </Select>
          <Select value={spec} onValueChange={(v) => setSpec(v as SpecFilter)}>
            <SelectTrigger aria-label="按模式筛选" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部模式（{items.length}）</SelectItem>
              <SelectItem value={RPG_SPEC}>单人对话（{rpgCount}）</SelectItem>
              <SelectItem value={STORY_SPEC}>剧情（{storyCount}）</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {visible.length === 0 ? (
          isFiltering ? (
            <EmptyState
              icon={spec === STORY_SPEC ? Compass : MessageSquare}
              title={spec === STORY_SPEC ? '还没有任何剧情会话' : '没有符合条件的会话'}
              description={
                spec === STORY_SPEC
                  ? '剧情会话要挂在一份世界观上。选一个世界观，导演会按它的角色群安排演出。'
                  : '换个关键词，或把状态 / 模式筛选切回「全部」试试。'
              }
              actions={
                spec === STORY_SPEC ? (
                  <>
                    <Button variant="primary" onClick={() => setDialogOpen(true)}>
                      <Compass className="size-4" aria-hidden="true" />
                      开一场剧情
                    </Button>
                    <Button variant="secondary" asChild>
                      <Link to="/worlds">
                        先去剧情世界看看
                        <ArrowRight className="size-4" aria-hidden="true" />
                      </Link>
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      lib.reset();
                      setStatus('all');
                      setSpec('all');
                    }}
                  >
                    清除筛选
                  </Button>
                )
              }
            />
          ) : (
            <EmptyState
              icon={MessageSquare}
              title="还没有任何会话"
              description="选一张角色卡就能开始单人对话；想演一场多角色的剧情，就挑一份世界观 —— 两种模式在同一个列表里。"
              actions={
                <>
                  <Button variant="primary" onClick={() => setDialogOpen(true)}>
                    <CirclePlus className="size-4" aria-hidden="true" />
                    开一场新会话
                  </Button>
                  <Button variant="secondary" asChild>
                    <Link to="/">
                      先去内容库挑角色卡
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </Link>
                  </Button>
                  <Button variant="ghost" asChild>
                    <Link to="/worlds">
                      <Compass className="size-4" aria-hidden="true" />
                      去剧情世界
                    </Link>
                  </Button>
                </>
              }
              hint="还没有内容？在首启向导里可以一次装好自带的示例卡与世界书。"
            />
          )
        ) : (
          <ul className="divide-y divide-border-soft overflow-hidden rounded-lg border border-border bg-surface">
            {visible.map((s) => {
              const story = isStorySession(s);
              const worldName = story ? worldTitle(s.world_id) : '';
              return (
                <li
                  key={s.id}
                  className="group/row flex items-center gap-3 px-3 py-3 motion-fast hover:bg-surface-warm"
                >
                  <button
                    type="button"
                    onClick={() => navigate(sessionHref(s))}
                    className="flex min-w-0 flex-1 items-center gap-3 text-left"
                  >
                    <span
                      className={cn(
                        'grid size-8 shrink-0 place-items-center rounded-md border text-muted',
                        story ? 'border-accent/30 bg-accent-subtle text-accent' : 'border-border bg-surface-warm',
                      )}
                    >
                      {story ? (
                        <Compass className="size-4" aria-hidden="true" />
                      ) : (
                        <MessageSquare className="size-4" aria-hidden="true" />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="min-w-0 truncate text-base font-medium text-fg">
                          {story && worldName ? worldName : s.scene.summary || '未命名会话'}
                        </span>
                        {/* 模式标签：剧情用 accent 与单人对话拉开区分度 */}
                        {story ? (
                          <Badge variant="accent" title="剧情模式：一轮里可能有多个角色依次开口">
                            剧情
                          </Badge>
                        ) : null}
                        <Badge
                          variant={s.status === 'active' ? 'success' : s.status === 'paused' ? 'warn' : 'outline'}
                        >
                          {STATUS_LABEL[s.status]}
                        </Badge>
                      </span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-meta">
                        <span className="truncate">
                          {[s.scene.location, s.scene.time].filter(Boolean).join(' · ') || '场景未命名'}
                        </span>
                        <span className="font-mono tabular-nums">{s.state_machine.turn} 轮</span>
                        {story ? (
                          <span className="inline-flex items-center gap-1">
                            <BookOpen className="size-3" aria-hidden="true" />
                            {s.scene.summary || '尚未开演'}
                          </span>
                        ) : (
                          <span>{s.worldbook_ids.length} 本世界书</span>
                        )}
                        <span>{relativeTime(s.updated_at)}</span>
                      </span>
                    </span>
                  </button>

                  <span className={cn('tech-meta hidden shrink-0 sm:block')}>
                    {s.memory.facts.length} 条记忆
                  </span>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${s.scene.summary || '会话'} 的更多操作`}
                        className="opacity-0 group-hover/row:opacity-100 focus:opacity-100"
                      >
                        <Ellipsis className="size-4" aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => navigate(sessionHref(s))}>
                        <ArrowRight className="size-4" aria-hidden="true" />
                        {story ? '继续这场剧情' : '继续这场会话'}
                      </DropdownMenuItem>
                      <DropdownMenuItem disabled={offline} onSelect={() => fork.mutate(s.id)}>
                        <GitFork className="size-4" aria-hidden="true" />
                        从末尾分叉
                      </DropdownMenuItem>
                      <DropdownMenuItem disabled={offline}>
                        <Pause className="size-4" aria-hidden="true" />
                        暂停（暂未接线）
                      </DropdownMenuItem>
                      <DropdownMenuItem disabled={offline}>
                        <Archive className="size-4" aria-hidden="true" />
                        归档（暂未接线）
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        destructive
                        disabled={offline}
                        onSelect={() => {
                          if (window.confirm('删除这场会话？消息与记忆会一起删除，角色卡不受影响。')) {
                            remove.mutate(s.id);
                          }
                        }}
                      >
                        <Trash2 className="size-4" aria-hidden="true" />
                        删除会话
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <NewSessionDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open && cardParam) {
            const next = new URLSearchParams(params);
            next.delete('card');
            setParams(next, { replace: true });
          }
        }}
        defaultCardId={cardParam}
        defaultMode={spec === STORY_SPEC ? 'story' : 'rpg'}
        onCreated={(s) => {
          setDialogOpen(false);
          void qc.invalidateQueries({ queryKey: ['sessions'] });
          navigate(sessionHref(s));
        }}
      />

      {items.length > 0 ? (
        <p className="flex items-center gap-1.5 px-6 pb-6 text-xs text-meta">
          <GitBranch className="size-3.5" aria-hidden="true" />
          在会话内用「分支树」可以在任意节点开新的故事线，原会话不受影响。
        </p>
      ) : null}
    </div>
  );
}
