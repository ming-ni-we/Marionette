import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/common/empty-state';
import { MessageBubble } from '@/components/session/message-bubble';
import { OpeningCard } from './opening-card';
import { SceneImageBlock } from './scene-image-block';
import { STATE_LABEL } from '@/mocks/fixtures';
import { CircleAlert, RefreshCw, Sparkles, BookOpen, UsersRound } from '@/components/icons';
import type { Message, SessionState, StorySnapshot, World } from '@/api/types';
import type { SpeakerIndex } from '@/hooks/use-speakers';
import type { SceneImage } from '@/hooks/use-chat-stream';

/**
 * 剧情阅读列。
 * -----------------------------------------------------------------------------
 * 与 1v1 `ReadingColumn` 的核心差别：**逐条按各自的 meta 分派渲染**。
 *
 * 一轮里可能连续出现 3 条 assistant 消息（旁白 + 两个角色），
 * 它们共用同一个 `turn` 但视觉形态完全不同。所以这里绝不做
 * 「把最后 N 条合成一块」之类的合并假设——每条消息自己说了算。
 *
 * 四路分派（顺序不可颠倒，`is_narration` 优先于 `beat_role`）：
 *   1. role === 'user'                  → 玩家气泡（右对齐，复用既有配色）
 *   2. beat_role === 'opening'          → 序幕卡片
 *   3. meta.is_narration === true
 *      或 beat_role === 'narration'     → 旁白（居中、斜体、无角色头）
 *   4. 其他 assistant                    → 角色气泡（左对齐 + 角色头）
 */
interface StoryReadingColumnProps {
  messages: Message[];
  state: SessionState;
  generating: boolean;
  error: string | null;
  speakers: SpeakerIndex;
  snapshot?: StorySnapshot | null;
  world?: World | null;
  /** 本轮流式收到的配图（S16-8）。回读路径走 `message.meta`，由本组件合并。 */
  sceneImages?: SceneImage[];
  onZoomImage?: (src: string, caption: string) => void;
  onRegenerate?: (messageId: string) => void;
  onRetry: () => void;
}

export function StoryReadingColumn({
  messages,
  state,
  generating,
  error,
  speakers,
  snapshot,
  world,
  sceneImages,
  onZoomImage,
  onRegenerate,
  onRetry,
}: StoryReadingColumnProps) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-[68ch] px-4 py-4">
        {messages.length === 0 ? (
          <StoryEmptyState world={world} />
        ) : (
          <div>
            {messages.map((msg) => {
              const image = resolveSceneImage(msg, sceneImages);
              return (
                <div key={msg.id}>
                  <StoryBeat
                    message={msg}
                    speakers={speakers}
                    snapshot={snapshot}
                    world={world}
                    onRegenerate={onRegenerate}
                  />
                  {image ? <SceneImageBlock image={image} onZoom={onZoomImage} /> : null}
                </div>
              );
            })}
          </div>
        )}

        {/* 生成中提示：多角色轮次时说明「还在排人」，否则用户以为卡住了 */}
        {generating ? (
          <p className="py-2 text-sm text-accent" aria-live="polite">
            {state === 'assembling'
              ? '正在装配剧情上下文（世界观 · 关系图 · 在场角色）…'
              : `${STATE_LABEL[state]}…多角色会依次开口`}
          </p>
        ) : null}

        {/* 就地错误条：已演出的内容保留不丢 */}
        {error ? (
          <div
            role="alert"
            className="mt-3 flex flex-wrap items-center gap-3 rounded-md border border-border bg-danger-subtle px-3 py-2.5"
          >
            <CircleAlert className="size-4 shrink-0 text-danger" aria-hidden="true" />
            <span className="min-w-0 flex-1 text-sm leading-relaxed text-fg-2">
              {error} —— 已经演出来的部分保留在上面，不会丢。
            </span>
            <Button variant="secondary" size="sm" onClick={onRetry}>
              <RefreshCw className="size-4" aria-hidden="true" />
              重试这一轮
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

/**
 * 合并两条配图来源，返回该消息该显示的图（没有则 `null`）。
 *
 * - **流式**：`image` 事件按 `message_id` 记在 `sceneImages` 里
 * - **回读**：`message.meta.image_asset_id`（后端出图时落库，刷新后仍在）
 *
 * 优先级给流式：它带着 `reason`（图注文案），回读只有 asset_id。
 * 两条路径共用同一个 `message_id` 锚点，所以同一张图不会被画两次。
 */
function resolveSceneImage(
  msg: Message,
  sceneImages: SceneImage[] | undefined,
): SceneImage | null {
  const streamed = sceneImages?.find((x) => x.messageId === msg.id);
  if (streamed) return streamed;

  const assetId = msg.meta?.image_asset_id;
  if (!assetId) return null;
  return { assetId, reason: 'node', messageId: msg.id };
}

/** 单条拍点：按 `meta` 分派到四种形态之一。 */
function StoryBeat({
  message,
  speakers,
  snapshot,
  world,
  onRegenerate,
}: {
  message: Message;
  speakers: SpeakerIndex;
  snapshot?: StorySnapshot | null;
  world?: World | null;
  onRegenerate?: (messageId: string) => void;
}) {
  const meta = message.meta ?? {};
  const streaming = message.status === 'streaming';

  /* ---- 1. 玩家 ---- */
  if (message.role === 'user') {
    return (
      <MessageBubble
        message={message}
        speakerName="你"
        onRegenerate={onRegenerate}
        streaming={streaming}
      />
    );
  }

  /* ---- system / tool：沿用 1v1 的分隔行样式 ---- */
  if (message.role === 'system' || message.role === 'tool') {
    return (
      <MessageBubble
        message={message}
        speakerName="系统"
        onRegenerate={onRegenerate}
        streaming={streaming}
      />
    );
  }

  /* ---- 2. 序幕 ---- */
  if (meta.beat_role === 'opening') {
    return <OpeningCard message={message} snapshot={snapshot} world={world} />;
  }

  /* ---- 3. 旁白 ----
     注意：判定要同时看 `is_narration` 与 `beat_role`。
     后端两条路径都会用（流式走 speaker_switch.is_narration，
     回读历史走 beat_role），只认一个会在某条路径上退化成角色气泡。 */
  const isNarration = meta.is_narration === true || meta.beat_role === 'narration';
  if (isNarration) {
    return <NarrationBlock content={message.content} streaming={streaming} />;
  }

  /* ---- 4. 角色气泡 ---- */
  const identity = speakers.get(meta.speaker_id, meta.speaker_name);
  return (
    <MessageBubble
      message={message}
      speakerName={identity.name}
      onRegenerate={onRegenerate}
      streaming={streaming}
    />
  );
}

/**
 * 旁白块：居中、无角色头、上下留白更大。
 * 用左对齐的正文（长段居中不可读）配合居中的窄版心与顶部分隔，形成「镜头切走」的观感。
 */
function NarrationBlock({ content, streaming }: { content: string; streaming: boolean }) {
  if (!content.trim() && !streaming) return null;
  return (
    <div className="my-4" aria-label="旁白">
      <div className="mx-auto max-w-[60ch] border-l-2 border-border-soft pl-4">
        <p className={cn('narrative text-fg-2', streaming && 'stream-caret')}>{content}</p>
      </div>
    </div>
  );
}

/** 空态：进入世界但还没开始演。 */
function StoryEmptyState({ world }: { world?: World | null }) {
  return (
    <EmptyState
      icon={BookOpen}
      title={world ? `《${world.title}》还没开演` : '这一场剧情还没有开始'}
      description={
        world?.opening
          ? '序幕会在你发出第一条输入后由导演铺开。下面是这个世界观自己写的引子：'
          : '在下面写你想做什么，AI 导演会安排在场角色依次回应。'
      }
      hint={
        world?.opening ? (
          <span className="narrative block text-left text-sm text-fg-2">{world.opening}</span>
        ) : (
          <span className="inline-flex items-center gap-1.5">
            <UsersRound className="size-3.5" aria-hidden="true" />
            一轮里可能有多个角色同时开口，导演会先说明他为什么这样安排。
          </span>
        )
      }
      actions={
        <span className="inline-flex items-center gap-1.5 text-sm text-muted">
          <Sparkles className="size-4" aria-hidden="true" />
          写下第一个动作
        </span>
      }
    />
  );
}
