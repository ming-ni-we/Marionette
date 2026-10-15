import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';

/**
 * 通用图片灯箱。
 * -----------------------------------------------------------------------------
 * 只是 `ui/dialog` 的一层薄封装 —— **刻意不自己实现弹层**。
 * Radix Dialog 已经处理好这些容易做漏的事，重写一遍只会引入新 bug：
 *   - `Esc` 关闭
 *   - 焦点陷阱（Tab 不会跑出弹层）与关闭后**焦点还原**到触发元素
 *   - `aria-modal` / `role="dialog"` 语义
 *   - 打开时锁滚动
 *
 * 本组件的职责只有两件：**大图 + 图注**，以及把无障碍标题接上。
 * reduced-motion 由 `tokens.css` 的全局规则统一降速，这里不额外处理。
 *
 * 复用方：剧情配图（`story-runtime`）、素材库（`asset-gallery`）。
 * 两处都需要「原图不被缩略图裁切」这一点，所以 `object-contain` 是硬要求，
 * 不能用 `object-cover`。
 */
interface LightboxProps {
  open: boolean;
  src: string;
  caption: string;
  onClose: () => void;
}

export function Lightbox({ open, src, caption, onClose }: LightboxProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent
        // 覆盖 Dialog 默认的卡片样式：灯箱要「无边框、无内边距、按图定宽」
        className="w-auto max-w-[min(92vw,1400px)] border-0 bg-transparent p-0 shadow-none"
      >
        {/* 标题对读屏可见、视觉隐藏（图注在下方已可见，重复显示反而啰嗦） */}
        <DialogTitle className="sr-only">{caption}</DialogTitle>
        <img
          src={src}
          alt={caption}
          className="block max-h-[82vh] w-auto max-w-full rounded-lg border border-border-soft object-contain"
        />
        {caption ? <p className="mt-3 text-center text-xs text-meta">{caption}</p> : null}
      </DialogContent>
    </Dialog>
  );
}
