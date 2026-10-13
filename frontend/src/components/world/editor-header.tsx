import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Compass, CircleCheck, TriangleAlert, ArrowLeft, Save, Play } from '@/components/icons';

/** 世界观编辑器顶栏（返回 · 标题 · 保存态 · 规模统计 · 保存 / 开演）。 */
export function WorldEditorHeader({
  title,
  isNew,
  demo,
  dirty,
  castCount,
  relationCount,
  nodeCount,
  saving,
  canSave,
  onSave,
  onPlay,
  playDisabled,
  playBlockReason,
}: {
  title: string;
  isNew: boolean;
  demo: boolean;
  dirty: boolean;
  castCount: number;
  relationCount: number;
  nodeCount: number;
  saving: boolean;
  canSave: boolean;
  onSave: () => void;
  /** 保存成功后才有意义：直接拿这个世界观开一局 */
  onPlay?: () => void;
  /** 开演前置条件是否满足（缺卡/缺预设时为 true，按钮禁用） */
  playDisabled?: boolean;
  /** 禁用原因，作为 title 提示 —— 别让用户对着灰按钮猜 */
  playBlockReason?: string;
}) {
  return (
    <header className="sticky top-0 z-sticky border-b border-border bg-surface/95 px-6 py-2.5 backdrop-blur-[2px]">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/">
            <ArrowLeft className="size-4" aria-hidden="true" />
            内容库
          </Link>
        </Button>
        <div className="flex min-w-0 items-center gap-2">
          <Compass className="size-4 shrink-0 text-muted" aria-hidden="true" />
          <span className="truncate text-md font-medium text-fg">{title || '未命名世界'}</span>
        </div>
        {isNew ? <Badge variant="accent">新建</Badge> : null}
        {demo ? <Badge variant="warn">演示数据</Badge> : null}
        <span
          className={cn(
            'inline-flex items-center gap-1.5 text-sm',
            dirty ? 'text-warn' : 'text-muted',
          )}
          aria-live="polite"
        >
          {dirty ? (
            <>
              <TriangleAlert className="size-3.5" aria-hidden="true" />
              有未保存修改
            </>
          ) : (
            <>
              <CircleCheck className="size-3.5" aria-hidden="true" />
              已保存
            </>
          )}
        </span>
        <span className="tech-meta ml-auto hidden sm:inline">
          {castCount} 角色 · {relationCount} 关系 · {nodeCount} 节点
        </span>
        <div className="flex items-center gap-2">
          <Button variant="primary" size="sm" onClick={onSave} loading={saving} disabled={!canSave}>
            <Save className="size-4" aria-hidden="true" />
            保存
          </Button>
          {!isNew && onPlay ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={onPlay}
              disabled={dirty || playDisabled}
              title={playBlockReason || (dirty ? '有未保存的修改，先保存再开演' : '用这个世界观开一局剧情')}
            >
              <Play className="size-4" aria-hidden="true" />
              开演
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
