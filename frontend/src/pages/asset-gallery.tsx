import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import { assetsApi, cardsApi } from '@/api/client';
import type { Asset, AssetKind } from '@/api/types';
import { SAMPLE_ASSETS, SAMPLE_CARDS } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';
import { PageHeader, SectionHeading } from '@/components/common/page-header';
import { LibraryToolbar } from '@/components/common/library-toolbar';
import { EmptyState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Images, ImagePlus, Sparkles } from '@/components/icons';
import { AssetCard } from '@/components/assets/asset-card';
import { ArchiveGuide } from '@/components/assets/archive-guide';
import { useLibraryController, aggregateTags } from '@/hooks/use-library';

export function AssetGalleryPage() {
  const lib = useLibraryController({ sort: 'created_at' });
  const [cardId, setCardId] = useState<string>('all');
  const [kind, setKind] = useState<AssetKind | 'all'>('all');

  const [assetsQ, cardsQ] = useQueries({
    queries: [
      {
        queryKey: ['assets', lib.searchQuery, cardId, kind],
        queryFn: () =>
          assetsApi.list({
            ...lib.searchQuery,
            card_id: cardId === 'all' ? undefined : cardId,
            kind: kind === 'all' ? undefined : kind,
          }),
        retry: false,
      },
      { queryKey: ['cards', 'picker'], queryFn: () => cardsApi.list({ limit: 100 }), retry: false },
    ],
  });

  const offline = assetsQ.isError;
  const cards = cardsQ.data?.items ?? (cardsQ.isError ? SAMPLE_CARDS : []);

  let items: Asset[] = assetsQ.data?.items ?? (offline ? SAMPLE_ASSETS : []);
  if (offline) {
    if (cardId !== 'all') items = items.filter((a) => a.card_id === cardId);
    if (kind !== 'all') items = items.filter((a) => a.kind === kind);
    if (lib.debouncedQuery) {
      const q = lib.debouncedQuery.toLowerCase();
      items = items.filter((a) => a.filename.toLowerCase().includes(q));
    }
  }

  const availableTags = aggregateTags(items.map((a) => ({ tags: a.tags })));
  const filtered =
    lib.tags.length > 0 ? items.filter((a) => lib.tags.every((t) => a.tags.includes(t))) : items;

  const cardName = (id: string | null) =>
    id ? (cards.find((c) => c.id === id)?.data.name ?? '未知角色') : '未归属角色';

  const remove = async (asset: Asset) => {
    if (offline) {
      toast.show('演示模式下不执行删除', '接上后端后这里会真的删除该资产。');
      return;
    }
    try {
      await assetsApi.remove(asset.id);
      toast.success('已删除资产');
      void assetsQ.refetch();
    } catch {
      toast.danger('删除失败', '后端没有确认这次删除。');
    }
  };

  return (
    <div className="min-h-dvh">
      <PageHeader
        title="角色图集"
        description="出图完成后由服务端自动归档到这里，按角色归位。你也可以手动上传立绘与背景，用关键词检索。"
        actions={
          <Button variant="secondary" asChild>
            <Link to="/sessions">
              <Sparkles className="size-4" aria-hidden="true" />
              去会话里出图
            </Link>
          </Button>
        }
        meta={
          <span className="tech-meta">
            {cards.length} 位角色 · {filtered.length} 张素材
          </span>
        }
      />

      {offline ? (
        <div className="border-b border-border-soft bg-warn-subtle px-6 py-2.5">
          <p className="text-sm leading-relaxed text-fg-2">
            <span className="font-medium text-warn">后端未连接</span> ——
            下面是演示条目（不含真实图片字节，只展示归档结构）。接上后端后会直接显示缩略图。
          </p>
        </div>
      ) : null}

      <div className="space-y-4 px-6 py-5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[240px] flex-1">
            <LibraryToolbar
              query={lib.query}
              onQueryChange={lib.setQuery}
              selectedTags={lib.tags}
              onSelectedTagsChange={lib.setTags}
              availableTags={availableTags}
              sort={lib.sort}
              onSortChange={lib.setSort}
              order={lib.order}
              onOrderChange={lib.setOrder}
              placeholder="搜索文件名或标签"
              resultCount={filtered.length}
            />
          </div>
          <Select value={cardId} onValueChange={setCardId}>
            <SelectTrigger aria-label="按角色筛选" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部角色</SelectItem>
              {cards.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.data.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={kind} onValueChange={(v) => setKind(v as AssetKind | 'all')}>
            <SelectTrigger aria-label="按类型筛选" className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部类型</SelectItem>
              <SelectItem value="avatar">头像</SelectItem>
              <SelectItem value="gallery">图集</SelectItem>
              <SelectItem value="generated">生成图</SelectItem>
              <SelectItem value="background">背景</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {filtered.length === 0 ? (
          <EmptyState
            icon={Images}
            title={offline ? '这个筛选下没有素材' : '还没有任何素材'}
            description="出图完成后会自动按角色归档进来。也可以现在手动上传一张立绘或背景，先把手上的图管起来。"
            actions={
              <>
                <Button variant="primary" disabled>
                  <ImagePlus className="size-4" aria-hidden="true" />
                  上传图片（待接线）
                </Button>
                <Button variant="secondary" asChild>
                  <Link to="/sessions">
                    <Sparkles className="size-4" aria-hidden="true" />
                    去会话里触发一次出图
                  </Link>
                </Button>
              </>
            }
            hint="出图的归档由服务端完成：任务变为 done 时自动写入图集，前端不参与拼装。"
          />
        ) : (
          <>
            <SectionHeading title="全部素材" count={filtered.length} hint="按创建时间倒序" />
            <ul className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {filtered.map((asset) => (
                <AssetCard
                  key={asset.id}
                  asset={asset}
                  offline={offline}
                  ownerName={cardName(asset.card_id)}
                  onRemove={(a) => void remove(a)}
                />
              ))}
            </ul>
          </>
        )}

        <ArchiveGuide />
      </div>
    </div>
  );
}
