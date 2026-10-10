import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * 合并 Tailwind 类名：clsx 处理条件类名，tailwind-merge 消解冲突。
 * 全项目统一入口（禁止在组件里自行拼接 className 字符串）。
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** 截断文本到指定长度，超出补省略号（用于卡片摘要/标题） */
export function truncate(text: string, max: number): string {
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** 相对时间（中文），用于"最近编辑/最近会话" */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Date.now() - then;
  const min = Math.floor(diff / 60000);
  if (min < 1) return '刚刚';
  if (min < 60) return `${min} 分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;
  const day = Math.floor(hour / 24);
  if (day < 30) return `${day} 天前`;
  return new Date(iso).toLocaleDateString('zh-CN');
}

/** 文件大小格式化 */
export function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/** Token 数格式化（千分位，配等宽字体） */
export function formatTokens(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n);
}

/** 生成幂等键（防重复提交 / 并发双击） */
export function makeIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** 复制到剪贴板，返回是否成功 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * 关键词高亮：把 query 按子串拆到 <mark>。
 * 注意必须先转义，避免注入；返回分段数组供 React 渲染（不使用 innerHTML）。
 */
export function splitHighlight(
  text: string,
  query: string,
): Array<{ text: string; hit: boolean }> {
  const q = query.trim();
  if (!q) return [{ text, hit: false }];
  const lower = text.toLowerCase();
  const lowerQ = q.toLowerCase();
  const parts: Array<{ text: string; hit: boolean }> = [];
  let cursor = 0;
  let idx = lower.indexOf(lowerQ, cursor);
  while (idx !== -1) {
    if (idx > cursor) parts.push({ text: text.slice(cursor, idx), hit: false });
    parts.push({ text: text.slice(idx, idx + q.length), hit: true });
    cursor = idx + q.length;
    idx = lower.indexOf(lowerQ, cursor);
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), hit: false });
  return parts;
}
