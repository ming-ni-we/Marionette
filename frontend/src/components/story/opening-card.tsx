import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { BookOpen } from '@/components/icons';
import type { Message, SceneStory, StorySnapshot, World } from '@/api/types';

interface OpeningCardProps {
  message: Message;
  /** 剧情快照（拿到就用真实场景，拿不到退回空） */
  snapshot?: StorySnapshot | null;
  /** 世界观（离线兜底时用） */
  world?: World | null;
  className?: string;
}

/**
 * 序幕卡片。
 * -----------------------------------------------------------------------------
 * 它和角色气泡的区别必须**一眼可辨**——这是玩家进入一个世界看到的第一块内容，
 * 如果长得像角色台词，玩家会以为苏晚在说话。
 *
 * 因此刻意做了三层区分：
 *   1) 整块居中 + 上下书挡线（`border-y`），视觉上自成一段
 *   2) 版心更窄（56ch < 阅读列 68ch），两侧留白强调「这是引子不是对话」
 *   3) 标题区先给「序幕」+ 场景标签，再给正文
 */
export function OpeningCard({ message, snapshot, world, className }: OpeningCardProps) {
  const scene: SceneStory | undefined = snapshot?.scene;
  const location = scene?.location || world?.setting?.locations?.[0] || '';
  const time = scene?.time || '';
  const mood = scene?.mood || '';
  const summary = scene?.summary || world?.setting?.summary || '';
  const hasMeta = Boolean(location || time || mood);

  return (
    <article
      className={cn(
        'my-6 border-y border-border-soft py-5',
        'motion-reduce:transition-none',
        className,
      )}
      aria-label="序幕"
    >
      <div className="mx-auto w-full max-w-[56ch] text-center">
        <div className="mb-3 flex items-center justify-center gap-2">
          <span className="h-px w-6 bg-border-soft" aria-hidden="true" />
          <span className="inline-flex items-center gap-1.5 text-xs font-medium tracking-wider text-accent">
            <BookOpen className="size-3.5" aria-hidden="true" />
            序幕
          </span>
          <span className="h-px w-6 bg-border-soft" aria-hidden="true" />
        </div>

        {hasMeta ? (
          <div className="mb-3 flex flex-wrap items-center justify-center gap-1.5">
            {location ? <Badge variant="outline">{location}</Badge> : null}
            {time ? <span className="tech-meta">{time}</span> : null}
            {mood ? <span className="text-xs text-muted">{mood}</span> : null}
          </div>
        ) : null}

        {/* 正文：居中 + 衬线 + 左对齐段落（纯居中长文不可读，只让块居中） */}
        <p className="narrative mx-auto text-left text-fg-2">{message.content}</p>

        {message.status === 'streaming' ? (
          <p className="mt-3 text-xs text-accent" aria-live="polite">
            正在铺开第一个场景…
          </p>
        ) : null}
        {message.status === 'incomplete' ? (
          <p className="mt-3 text-xs text-warn">这一段没有生成完</p>
        ) : null}

        {summary ? (
          <p className="mx-auto mt-4 max-w-[52ch] border-t border-border-soft pt-3 text-xs leading-relaxed text-meta">
            {summary}
          </p>
        ) : null}
      </div>
    </article>
  );
}
