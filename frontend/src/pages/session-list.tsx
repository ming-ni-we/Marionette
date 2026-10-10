import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cn, relativeTime } from '@/lib/utils';
import { sessionsApi } from '@/api/client';
import type { Session, SessionStatus } from '@/api/types';
import { SAMPLE_SESSIONS } from '@/mocks/fixtures';
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
} from '@/components/icons';
import { useLibraryController } from '@/hooks/use-library';

const STATUS_LABEL: Record<SessionStatus, string> = {
  active: '进行中',
  paused: '已暂停',
  archived: '已归档',
};

export function SessionListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const lib = useLibraryController({ sort: 'last_message_at' });
  const [status, setStatus] = useState<SessionStatus | 'all'>('all');
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

  const offline = query.isError;
  const items: Session[] = offline
    ? SAMPLE_SESSIONS.filter((s) => (status === 'all' ? true : s.status === status))
    : query.data?.items ?? [];

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
      navigate(`/sessions/${s.id}`);
    },
    onError: () => toast.danger('分支失败', '后端拒绝了这次分叉请求。'),
  });

  // 会话没有标签维度，隐藏标签筛选器与已选 chips
  const isFiltering = Boolean(lib.debouncedQuery) || status !== 'all';

  return (
    <div className="flex min-h-dvh flex-col">
      <PageHeader
        title="会话"
        description="每场会话绑定一张角色卡、一套预设与若干本世界书。世界书命中与记忆都会在会话内可查。"
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
        </div>

        {items.length === 0 ? (
          isFiltering ? (
            <EmptyState
              icon={MessageSquare}
              title="没有符合条件的会话"
              description="换个关键词或把状态筛选切回「全部」试试。"
              actions={
                <Button
                  variant="secondary"
                  onClick={() => {
                    lib.reset();
                    setStatus('all');
                  }}
                >
                  清除筛选
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={MessageSquare}
              title="还没有任何会话"
              description="挑一张角色卡就能开始 —— 预设与世界书会自动带上默认值，第一句话可以直接发。"
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
                </>
              }
              hint="还没有角色卡？在首启向导里可以一次装好自带的示例卡与世界书。"
            />
          )
        ) : (
          <ul className="divide-y divide-border-soft overflow-hidden rounded-lg border border-border bg-surface">
            {items.map((s) => (
              <li key={s.id} className="group/row flex items-center gap-3 px-3 py-3 motion-fast hover:bg-surface-warm">
                <button
                  type="button"
                  onClick={() => navigate(`/sessions/${s.id}`)}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-md border border-border bg-surface-warm text-muted">
                    <MessageSquare className="size-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="min-w-0 truncate text-base font-medium text-fg">
                        {s.scene.summary || '未命名会话'}
                      </span>
                      <Badge variant={s.status === 'active' ? 'success' : s.status === 'paused' ? 'warn' : 'outline'}>
                        {STATUS_LABEL[s.status]}
                      </Badge>
                    </span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-meta">
                      <span className="truncate">
                        {s.scene.location}
                        {s.scene.time ? ` · ${s.scene.time}` : ''}
                      </span>
                      <span className="font-mono tabular-nums">{s.state_machine.turn} 轮</span>
                      <span>{s.worldbook_ids.length} 本世界书</span>
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
                    <DropdownMenuItem onSelect={() => navigate(`/sessions/${s.id}`)}>
                      <ArrowRight className="size-4" aria-hidden="true" />
                      继续这场会话
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
            ))}
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
        onCreated={(s) => {
          setDialogOpen(false);
          void qc.invalidateQueries({ queryKey: ['sessions'] });
          navigate(`/sessions/${s.id}`);
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
