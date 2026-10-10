import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { SectionHeading } from '@/components/common/page-header';
import { Crop, ExternalLink } from '@/components/icons';

/** 出图与归档说明（同时充当「如何拿到第一张素材」的入口引导）。 */
export function ArchiveGuide() {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <SectionHeading title="出图与归档" hint="轻量钩子：触发 → 出图 → 自动进图集" />
      <ol className="space-y-1.5 text-sm leading-relaxed text-muted">
        <li className="flex items-start gap-2">
          <span className="tech-meta mt-0.5 shrink-0">01</span>
          在预设里开启「出图钩子」，选手动 / 每 N 轮 / 场景切换触发。
        </li>
        <li className="flex items-start gap-2">
          <span className="tech-meta mt-0.5 shrink-0">02</span>
          会话中出现 `image` 事件时，图片会内嵌进对话；同时自动登记为
          <code className="mx-1 font-mono text-fg-2">kind=generated</code>资产。
        </li>
        <li className="flex items-start gap-2">
          <span className="tech-meta mt-0.5 shrink-0">03</span>
          归档由服务端完成并回填角色 —— 所以这里永远能按角色找到它。
        </li>
      </ol>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="ghost" size="sm" disabled>
          <Crop className="size-4" aria-hidden="true" />
          批量裁剪（待在设置中接线）
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/settings">
            <ExternalLink className="size-4" aria-hidden="true" />
            去设置里配置出图后端
          </Link>
        </Button>
      </div>
    </div>
  );
}
