import type { ReactNode } from 'react';

/**
 * 「后端未连接」离线提示条（统一版式）。
 * 内容库 / 会话列表 / 素材库共用同一套描边、底色与文案层级，
 * 避免各页各写一份导致视觉漂移。
 */
export function OfflineBanner({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-border-soft bg-warn-subtle px-6 py-2.5" role="status">
      <p className="text-sm leading-relaxed text-fg-2">
        <span className="font-medium text-warn">后端未连接</span> —— {children}
      </p>
    </div>
  );
}
