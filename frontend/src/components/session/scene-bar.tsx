import type { Session } from '@/api/types';
import { Badge } from '@/components/ui/badge';

/** 场景条：地点 / 时间 / 摘要 + 演示数据标注（仅在非沉浸模式显示） */
export function SceneBar({
  session,
  offline,
  usedDemoFallback,
}: {
  session: Session;
  offline: boolean;
  usedDemoFallback: boolean;
}) {
  if (!session.scene.summary) return null;
  return (
    <div className="border-b border-border-soft bg-surface px-4 py-2">
      <div className="mx-auto flex w-full max-w-[68ch] flex-wrap items-center gap-2">
        <Badge variant="outline">{session.scene.location || '未设定地点'}</Badge>
        {session.scene.time ? <span className="tech-meta">{session.scene.time}</span> : null}
        <span className="text-sm text-muted">{session.scene.summary}</span>
        {usedDemoFallback ? <Badge variant="warn">演示数据（未找到该会话）</Badge> : null}
        {offline && !usedDemoFallback ? <Badge variant="warn">演示数据</Badge> : null}
      </div>
    </div>
  );
}
