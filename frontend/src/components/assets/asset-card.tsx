import { cn, formatBytes, relativeTime, copyText } from '@/lib/utils';
import { assetsApi } from '@/api/client';
import type { Asset, AssetKind } from '@/api/types';
import { toast } from '@/stores/ui';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Images, Sparkles, Trash2, Copy, UserRound, Maximize2 } from '@/components/icons';

export const KIND_LABEL: Record<AssetKind, string> = {
  avatar: '头像',
  gallery: '图集',
  generated: '生成图',
  background: '背景',
};

/** 单张素材卡片（缩略/占位 · 类型徽标 · 悬浮操作 · 元信息）。 */
export function AssetCard({
  asset,
  offline,
  ownerName,
  onRemove,
  onPreview,
}: {
  asset: Asset;
  offline: boolean;
  ownerName: string;
  onRemove: (asset: Asset) => void;
  /**
   * 点击缩略图 / 放大按钮 → 打开灯箱看完整图（不裁切）。
   * `offline`（演示数据）没有真实图片字节，不接线。
   */
  onPreview?: (asset: Asset) => void;
}) {
  const dims = asset.meta as { width?: number; height?: number };
  const previewable = Boolean(onPreview) && !offline;
  return (
    <li
      className={cn(
        'group/asset overflow-hidden rounded-lg border border-border bg-surface motion-fast hover:border-border-strong',
      )}
    >
      <div className="relative aspect-square bg-surface-sunken">
        {offline ? (
          <span className="grid size-full place-items-center text-meta">
            <span className="flex flex-col items-center gap-2">
              <Images className="size-6" aria-hidden="true" />
              <span className="max-w-[90%] truncate px-2 font-mono text-xs">{asset.filename}</span>
            </span>
          </span>
        ) : previewable ? (
          // 缩略图用 `object-cover`（方格整齐），点开才给原图 —— 所以入口必须显式存在，
          // 否则用户看到的是裁切版、也没有办法看到完整版。
          <button
            type="button"
            onClick={() => onPreview?.(asset)}
            aria-label={`查看 ${asset.filename} 完整图片`}
            className="block size-full cursor-zoom-in focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent-ring"
          >
            <img
              src={assetsApi.contentUrl(asset.id)}
              alt={asset.filename}
              loading="lazy"
              className="size-full object-cover"
            />
          </button>
        ) : (
          <img
            src={assetsApi.contentUrl(asset.id)}
            alt={asset.filename}
            loading="lazy"
            className="size-full object-cover"
          />
        )}
        <span className="absolute left-2 top-2">
          <Badge variant={asset.kind === 'generated' ? 'accent' : 'neutral'}>
            {asset.kind === 'generated' ? <Sparkles className="size-3" aria-hidden="true" /> : null}
            {KIND_LABEL[asset.kind]}
          </Badge>
        </span>
        <div className="absolute inset-x-0 bottom-0 flex justify-end gap-1 bg-scrim p-1.5 opacity-0 transition-opacity duration-[var(--dur-fast)] group-hover/asset:opacity-100 focus-within:opacity-100">
          {previewable ? (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`查看 ${asset.filename} 完整图片`}
              className="text-fg"
              onClick={() => onPreview?.(asset)}
            >
              <Maximize2 className="size-3.5" aria-hidden="true" />
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`复制 ${asset.filename} 的链接`}
            className="text-fg"
            onClick={async () => {
              const ok = await copyText(assetsApi.contentUrl(asset.id));
              if (ok) toast.success('已复制图片链接');
              else toast.danger('复制失败', '浏览器不允许访问剪贴板。');
            }}
          >
            <Copy className="size-3.5" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`删除 ${asset.filename}`}
            className="text-fg"
            onClick={() => onRemove(asset)}
          >
            <Trash2 className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <div className="space-y-1 p-2.5">
        <p className="truncate font-mono text-xs text-fg-2" title={asset.filename}>
          {asset.filename}
        </p>
        <p className="flex items-center gap-1.5 text-xs text-meta">
          <UserRound className="size-3" aria-hidden="true" />
          <span className="truncate">{ownerName}</span>
        </p>
        <p className="flex flex-wrap items-center gap-x-2 text-xs text-meta">
          {dims.width && dims.height ? (
            <span className="font-mono tabular-nums">
              {dims.width}×{dims.height}
            </span>
          ) : null}
          <span className="font-mono tabular-nums">{formatBytes(asset.size_bytes)}</span>
          <span>{relativeTime(asset.created_at)}</span>
        </p>
        {asset.tags.length > 0 ? (
          <p className="flex flex-wrap gap-1 pt-0.5">
            {asset.tags.slice(0, 3).map((t) => (
              <span key={t} className="rounded-xs border border-border-soft px-1 text-xs text-muted">
                {t}
              </span>
            ))}
          </p>
        ) : null}
      </div>
    </li>
  );
}
