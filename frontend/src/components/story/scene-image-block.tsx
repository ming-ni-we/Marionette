import { useState } from 'react';
import { assetsApi } from '@/api/client/resources';
import { Images } from '@/components/icons';
import type { SceneImage } from '@/hooks/use-chat-stream';

/**
 * 剧情配图块（S16 步骤 8）。
 * -----------------------------------------------------------------------------
 * 由后端自动生成（节点触发 / 新角色登场）或玩家显式请求，随 `image` 事件到达，
 * 也可从 `message.meta.image_asset_id` 回读。**独立成段**渲染：居中、窄版心，
 * 与 `NarrationBlock` 同一套版式语言 —— 图片是「镜头」，不是某个角色的台词，
 * 所以它不属于任何气泡，自带留白自成一段。
 *
 * 三个务实决定：
 *   1. **取图走同源直链**（`assetsApi.contentUrl`）。会话 Cookie 是 HttpOnly，
 *      浏览器发 `<img>` 请求时自动携带，不需要 fetch+blob 那套。
 *   2. **`onError` 落到占位**。出图是异步的、资产可能被清理，碎图比没有图更难看。
 *   3. **图注用 `reason`**。告诉玩家这张图为什么出现（角色登场 / 剧情节点），
 *      否则突然插一张图会显得突兀。
 */
interface SceneImageBlockProps {
  image: SceneImage;
  /** 点击放大；由页面注入灯箱（组件本身不认识灯箱，便于单测与复用） */
  onZoom?: (src: string, caption: string) => void;
}

/** 出图原因 → 中文图注。 */
const REASON_LABEL: Record<SceneImage['reason'], string> = {
  cast: '角色登场',
  node: '剧情节点',
  manual: '手动绘制',
};

export function SceneImageBlock({ image, onZoom }: SceneImageBlockProps) {
  const [failed, setFailed] = useState(false);
  const caption = REASON_LABEL[image.reason] ?? REASON_LABEL.node;
  const src = assetsApi.contentUrl(image.assetId);
  const zoomable = Boolean(onZoom) && !failed;

  return (
    <figure className="my-5" data-scene-image={image.messageId}>
      <div className="mx-auto max-w-[60ch] overflow-hidden rounded-lg border border-border-soft bg-surface-sunken">
        {failed ? (
          <div
            role="img"
            aria-label={`${caption}配图加载失败`}
            className="grid aspect-video place-items-center text-muted"
          >
            <span className="flex flex-col items-center gap-2">
              <Images className="size-6" aria-hidden="true" />
              <span className="text-xs">配图未能加载</span>
            </span>
          </div>
        ) : zoomable ? (
          <button
            type="button"
            onClick={() => onZoom?.(src, caption)}
            aria-label={`放大查看${caption}配图`}
            className="block w-full cursor-zoom-in focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ring"
          >
            <img
              src={src}
              alt={caption}
              loading="lazy"
              onError={() => setFailed(true)}
              className="block w-full object-cover"
            />
          </button>
        ) : (
          <img
            src={src}
            alt={caption}
            loading="lazy"
            onError={() => setFailed(true)}
            className="block w-full object-cover"
          />
        )}
      </div>
      <figcaption className="mt-2 text-center text-xs text-meta">{caption}</figcaption>
    </figure>
  );
}
