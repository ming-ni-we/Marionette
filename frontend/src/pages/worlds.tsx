import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { worldsApi } from '@/api/client';
import type { World } from '@/api/types';
import { PageHeader } from '@/components/common/page-header';
import { EmptyState, ErrorState } from '@/components/common/empty-state';
import { OfflineBanner } from '@/components/common/offline-banner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Compass, CirclePlus, UsersRound, Network, ListTree, Pencil } from '@/components/icons';

/** 单张世界观卡：把「规模」直接摆出来，让用户一眼看出这个世界写得多厚。 */
function WorldCard({ world }: { world: World }) {
  const cast = world.cast?.length ?? 0;
  const relations = world.relations?.length ?? 0;
  const nodes = world.outline?.nodes?.length ?? 0;
  const locations = world.setting?.locations?.length ?? 0;

  return (
    <li className="flex flex-col rounded-md border border-border bg-surface p-4 motion-fast hover:border-border-strong">
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 text-md font-medium tracking-tight text-fg">
          <Link to={`/worlds/${world.id}`} className="hover:text-accent">
            {world.title || '未命名世界'}
          </Link>
        </h3>
        <Button variant="ghost" size="sm" asChild className="shrink-0">
          <Link to={`/worlds/${world.id}`} aria-label={`编辑 ${world.title || '未命名世界'}`}>
            <Pencil className="size-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>

      <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted">
        {world.setting?.summary || '还没有写总览。点进去补一句，导演会看得更准。'}
      </p>

      <dl className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-meta">
        <div className="flex items-center gap-1">
          <UsersRound className="size-3.5" aria-hidden="true" />
          <dt className="sr-only">角色数</dt>
          <dd className="font-mono tabular-nums">{cast} 角色</dd>
        </div>
        <div className="flex items-center gap-1">
          <Network className="size-3.5" aria-hidden="true" />
          <dt className="sr-only">关系数</dt>
          <dd className="font-mono tabular-nums">{relations} 关系</dd>
        </div>
        <div className="flex items-center gap-1">
          <ListTree className="size-3.5" aria-hidden="true" />
          <dt className="sr-only">节点数</dt>
          <dd className="font-mono tabular-nums">{nodes} 节点</dd>
        </div>
        {locations > 0 ? (
          <div className="flex items-center gap-1">
            <Compass className="size-3.5" aria-hidden="true" />
            <dt className="sr-only">地点数</dt>
            <dd className="font-mono tabular-nums">{locations} 地点</dd>
          </div>
        ) : null}
      </dl>

      {world.tags?.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {world.tags.slice(0, 5).map((tag) => (
            <Badge key={tag} variant="neutral">
              {tag}
            </Badge>
          ))}
        </div>
      ) : null}
    </li>
  );
}

/**
 * 世界观列表。
 *
 * 与内容库（workspace）的分工：内容库是「所有东西混在一起看」，这里是
 * 「专门管理剧情世界」的工作面——因为世界观的编辑体验是表单式的多区块，
 * 与卡/世界书的单文档编辑差异很大，混在内容库里会互相干扰。
 */
export function WorldsPage() {
  const query = useQuery({
    queryKey: ['worlds'],
    queryFn: () => worldsApi.list({ limit: 100 }),
    retry: false,
  });

  const worlds = useMemo(() => query.data?.items ?? [], [query.data]);

  return (
    <div className="flex min-h-dvh flex-col">
      <PageHeader
        title="剧情世界"
        description="一个世界 = 一套时空设定 + 一群角色 + 一张关系网。AI 导演只能在这个边界内安排戏份。"
        actions={
          <Button variant="primary" size="sm" asChild>
            <Link to="/worlds/new">
              <CirclePlus className="size-4" aria-hidden="true" />
              新建世界
            </Link>
          </Button>
        }
      />

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-5xl px-6 py-5">
          {query.isError ? (
            <OfflineBanner>
              剧情世界的编辑依赖后端存储，离线时无法新建或修改。下面没有内容可展示。
            </OfflineBanner>
          ) : null}

          {query.isError ? (
            <ErrorState
              description="没能从后端读到世界观列表。剧情世界的编辑依赖后端存储，离线时无法新建或修改。"
              actions={
                <Button variant="secondary" onClick={() => void query.refetch()}>
                  重试
                </Button>
              }
            />
          ) : query.isLoading ? (
            <p className="text-sm text-meta">正在读取…</p>
          ) : worlds.length === 0 ? (
            <EmptyState
              icon={Compass}
              title="还没有任何世界"
              description="建一个世界，填上时空、角色和关系，就能开始一局由 AI 导演编排的多角色剧情——不再是单人对话。"
              actions={
                <Button variant="primary" asChild>
                  <Link to="/worlds/new">
                    <CirclePlus className="size-4" aria-hidden="true" />
                    新建第一个世界
                  </Link>
                </Button>
              }
            />
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {worlds.map((world) => (
                <WorldCard key={world.id} world={world} />
              ))}
            </ul>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
