import { cn, truncate } from '@/lib/utils';
import { Sparkles, UserRound, Info } from '@/components/icons';
import type { CardData } from '@/api/types';

/** 粗略 token 估算：中文约 1.6 字/token，英文约 4 字符/token。仅用于即时反馈，非精确值。 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  const cjk = (text.match(/[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]/g) ?? []).length;
  const rest = text.length - cjk;
  return Math.ceil(cjk / 1.6 + rest / 4);
}

/** 解析 mes_example：把 {{user}}: / {{char}}: 行对成示例对话 */
export function parseExamples(mesExample: string): Array<{ role: 'user' | 'assistant'; text: string }> {
  if (!mesExample.trim()) return [];
  const lines = mesExample.split('\n');
  const out: Array<{ role: 'user' | 'assistant'; text: string }> = [];
  for (const line of lines) {
    const m = line.match(/^\s*\{\{(user|char)\}\}\s*[:：]\s*(.*)$/i);
    if (m) {
      out.push({ role: m[1].toLowerCase() === 'user' ? 'user' : 'assistant', text: m[2] });
    } else if (out.length > 0 && line.trim()) {
      out[out.length - 1].text += `\n${line}`;
    }
  }
  return out;
}

interface CardPreviewProps {
  data: CardData;
  /** 用户人设名（默认"你"） */
  userName?: string;
  className?: string;
}

/**
 * 实时气泡预览（docs/03-uiux.md §7.2）。
 * 用真实聊天气泡渲染"当前设定会产生什么效果"，解决"我写的这段到底影响什么"。
 */
export function CardPreview({ data, userName = '你', className }: CardPreviewProps) {
  const name = data.name.trim() || '（未命名角色）';
  const firstMes = data.first_mes.trim();
  const examples = parseExamples(data.mes_example);
  const firstExample = examples.find((e) => e.role === 'assistant');

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center gap-1.5 label-caps">
        <Sparkles className="size-3.5" aria-hidden="true" />
        实时预览
      </div>

      <div className="rounded-lg border border-border bg-reading-surface p-3">
        {/* 角色头部 */}
        <div className="mb-3 flex items-center gap-2 border-b border-border-soft pb-2.5">
          <span className="grid size-8 place-items-center rounded-md border border-border bg-surface text-accent">
            {name.slice(0, 1)}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-base font-medium text-fg">{name}</span>
            <span className="block truncate text-xs text-meta">
              {data.tags.length > 0 ? data.tags.slice(0, 3).join(' · ') : '未打标签'}
            </span>
          </span>
        </div>

        {/* 场景 */}
        {data.scenario.trim() ? (
          <p className="mb-3 rounded-sm border border-border-soft bg-surface-sunken px-2.5 py-2 text-xs leading-relaxed text-muted">
            <span className="font-medium text-fg-2">场景 · </span>
            {truncate(data.scenario.replace(/\s+/g, ' '), 110)}
          </p>
        ) : null}

        {/* 开场白 */}
        {firstMes ? (
          <div className="flex gap-2.5">
            <span
              aria-hidden="true"
              className="grid size-6 shrink-0 place-items-center rounded-md border border-border bg-surface text-xs text-accent"
            >
              {name.slice(0, 1)}
            </span>
            <div className="min-w-0">
              <div className="mb-1 text-xs text-muted">{name}</div>
              <p className="narrative rounded-md border border-border-soft bg-surface px-2.5 py-2 text-sm">
                {firstMes}
              </p>
            </div>
          </div>
        ) : (
          <p className="rounded-sm border border-dashed border-border px-2.5 py-3 text-xs leading-relaxed text-muted">
            还没有开场白。没有开场白时，会话开始时角色不会主动说话 —— 你可以先写一句她"推门时正在做什么"。
          </p>
        )}

        {/* 示例对话 */}
        {firstExample ? (
          <div className="mt-3 space-y-2 border-t border-border-soft pt-3">
            <div className="flex flex-row-reverse gap-2.5">
              <span
                aria-hidden="true"
                className="grid size-6 shrink-0 place-items-center rounded-md border border-border bg-surface-warm text-xs text-muted"
              >
                你
              </span>
              <p className="max-w-[46ch] rounded-md border border-border bg-surface px-2.5 py-2 text-sm leading-relaxed text-fg">
                {truncate(firstExample.text.replace(/\s+/g, ' '), 90)}
              </p>
            </div>
            <p className="text-center text-xs text-meta">例子里角色的回应方式，就是它会学到的说话风格</p>
          </div>
        ) : null}
      </div>

      <p className="flex items-start gap-1.5 text-xs leading-relaxed text-meta">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        预览用的是真实气泡样式，但不会调用模型 —— 想验证真实效果，用顶部「试开一场会话」。
      </p>

      {/* 用户人设位 */}
      <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-2">
        <UserRound className="size-3.5 shrink-0 text-muted" aria-hidden="true" />
        <span className="text-xs text-muted">
          当前你以「<span className="text-fg-2">{userName}</span>」的身份对话
        </span>
      </div>
    </div>
  );
}
