import type { Session } from '@/api/types';

/** 离线演示数据的本地筛选（后端不可达时，让工具条仍然真的可用）。 */

export function matchText(haystack: string, q: string): boolean {
  return haystack.toLowerCase().includes(q.toLowerCase());
}

/** 匹配 name / description / tags，并做标签 AND 过滤 */
export function demoFilter<T extends { data: { name: string; description?: string; tags?: string[] } }>(
  items: T[],
  q: string,
  tags: string[],
): T[] {
  return items.filter((it) => {
    const okText =
      q.trim() === '' ||
      matchText(it.data.name, q) ||
      matchText(it.data.description ?? '', q) ||
      (it.data.tags ?? []).some((t) => matchText(t, q));
    const okTags = tags.every((t) => (it.data.tags ?? []).includes(t));
    return okText && okTags;
  });
}

/** 演示会话按关键词收窄（匹配场景摘要与地点） */
export function filterDemoSessions(items: Session[], q: string): Session[] {
  if (!q.trim()) return items;
  const needle = q.toLowerCase();
  return items.filter(
    (s) =>
      s.scene.summary.toLowerCase().includes(needle) || s.scene.location.toLowerCase().includes(needle),
  );
}
