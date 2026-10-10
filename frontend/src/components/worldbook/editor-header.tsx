import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { BookOpen, CircleCheck, TriangleAlert, ArrowLeft, Save } from '@/components/icons';

/** 世界书编辑器顶栏（返回 · 标题 · 保存态 · 统计 · 保存）。 */
export function WorldBookHeader({
  name,
  isNew,
  demo,
  dirty,
  entriesLength,
  enabledCount,
  budget,
  saving,
  onSave,
}: {
  name: string;
  isNew: boolean;
  demo: boolean;
  dirty: boolean;
  entriesLength: number;
  enabledCount: number;
  budget: number;
  saving: boolean;
  onSave: () => void;
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
        <div className="flex items-center gap-2">
          <BookOpen className="size-4 text-muted" aria-hidden="true" />
          <span className="text-md font-medium text-fg">{name || '未命名世界书'}</span>
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
        <span className="tech-meta ml-auto">
          {entriesLength} 条 · {enabledCount} 条启用 · 预算 {budget}
        </span>
        <Button variant="primary" size="sm" onClick={onSave} loading={saving}>
          <Save className="size-4" aria-hidden="true" />
          保存
        </Button>
      </div>
    </header>
  );
}
