import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { sessionsApi } from '@/api/client';
import { SAMPLE_WORLDS, SAMPLE_SESSIONS } from '@/mocks/fixtures';
import { toast, useUiStore } from '@/stores/ui';
import { useChatStream } from '@/hooks/use-chat-stream';
import { useSpeakers } from '@/hooks/use-speakers';
import { CastStrip } from '@/components/story/cast-strip';
import { ActionDock } from '@/components/story/action-dock';
import { DirectorPanel, DirectorCue } from '@/components/story/director-panel';
import { NodeBanner } from '@/components/story/node-banner';
import { StoryReadingColumn } from '@/components/story/story-reading-column';
import { OfflineBanner } from '@/components/common/offline-banner';
import { ErrorState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, Compass, Minimize2, RefreshCw } from '@/components/icons';
import type { CastMember, StorySnapshot } from '@/api/types';

/**
 * 剧情演出页（`/stories/:id`）—— 多角色 AI 导演驱动的游玩界面。
 * -----------------------------------------------------------------------------
 * 与 1v1 `SessionRuntimePage` 的关系：
 *   两者共用 `useChatStream` 这一套流式状态机（S10 已改造完毕，剧情事件是它的超集），
 *   差别只在**渲染层与底部交互层**：
 *     - 1v1  ：单一角色 → `ReadingColumn` + `Composer`
 *     - 剧情：多角色轮演 → `StoryReadingColumn`（逐条按 meta 分派）+ `ActionDock`
 *
 * 因此这个页面**不重写任何流式逻辑**：`delta` 按 `speaker_id` 落点、
 * `done` 收口多条 streaming 残留，这两个坑 S10 已经填好了。
 *
 * 首屏额外做一件事：拉 `GET /sessions/{id}/story` 拿剧情快照，用于
 *   1) 顶部展示真实场景（location / mood）
 *   2) 角色头配色按 cast 稳定映射（不随出场顺序变色）
 *   3) 玩家打开页面时即使消息为空，也能看到世界观自己的序幕引子
 */
export function StoryRuntimePage() {
  const { id = '' } = useParams();
  const setDensity = useUiStore((s) => s.setDensity);
  const immersive = useUiStore((s) => s.immersive);
  const setImmersive = useUiStore((s) => s.setImmersive);

  /* ---------------------------------------------------- 数据 */
  const query = useQuery({
    queryKey: ['session', id],
    queryFn: () => sessionsApi.get(id),
    retry: false,
  });

  const storyQuery = useQuery({
    queryKey: ['session-story', id],
    queryFn: () => sessionsApi.getStory(id),
    retry: false,
    enabled: Boolean(id),
  });

  const offline = query.isError;
  const demoSession = SAMPLE_SESSIONS.find((s) => s.id === id);
  const session = query.data ?? (offline ? demoSession ?? SAMPLE_SESSIONS[0] : undefined);
  const usedDemoFallback = offline && !demoSession;

  const snapshot: StorySnapshot | null = storyQuery.data ?? null;
  const world = useMemo(() => {
    const wid = session?.world_id;
    if (!wid) return SAMPLE_WORLDS[0];
    return SAMPLE_WORLDS.find((w) => w.id === wid) ?? null;
  }, [session?.world_id]);

  /* ---------------------------------------------------- 流式状态机（复用） */
  // storyMode：消息行由后端建（「N 个说话者 = N 条消息」），前端不预建空气泡
  const chat = useChatStream({ sessionId: id, offline, storyMode: true });
  const [directorOpen, setDirectorOpen] = useState(false);
  const seededRef = useRef<string | null>(null);

  const { setMessages, setWorldInfoHits, setUsage, setError, setState, setStorySnapshot } = chat;

  // 运行端切到 session 密度；离开恢复 studio
  useEffect(() => {
    setDensity('session');
    return () => setDensity('studio');
  }, [setDensity]);

  // 首屏：把会话自身的消息灌进流式态（与 1v1 一致的播种语义）
  useEffect(() => {
    if (session && seededRef.current !== session.id) {
      setMessages(session.messages);
      setWorldInfoHits(Object.keys(session.triggered_entries ?? {}).length);
      setUsage({ prompt_tokens: 0, completion_tokens: 0 });
      setError(null);
      setState('idle');
      seededRef.current = session.id;
    }
  }, [session, setMessages, setWorldInfoHits, setUsage, setError, setState]);

  // 快照回来 → 回填剧情态（在场角色 / 关系），供角色头稳定配色
  useEffect(() => {
    if (!snapshot) return;
    setStorySnapshot({
      story: snapshot.story,
      relations: snapshot.relations,
      cast: snapshot.cast,
    });
  }, [snapshot, setStorySnapshot]);

  // 沉浸模式 Esc 退出
  useEffect(() => {
    if (!immersive) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setImmersive(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [immersive, setImmersive]);

  /* ---------------------------------------------------- 派生 */

  /**
   * 角色名单：以快照 `cast` 为基准（作者定义顺序 → 配色稳定），
   * 但**必须并入 `director.speakers`**——导演本轮可能让快照里还没有的角色出场。
   * 漏掉这一步，新角色会拿到中性灰而不是自己的色。
   */
  const cast = useMemo<CastMember[]>(() => {
    const base: CastMember[] = snapshot?.cast ?? world?.cast?.map((c) => ({
      id: c.id,
      name: c.name,
      role: c.role,
      voice: c.voice,
      present: true,
    })) ?? [];
    const seen = new Set(base.map((c) => c.id));
    const extra: CastMember[] = [];
    for (const s of chat.speakers) {
      if (!s.id || seen.has(s.id)) continue;
      seen.add(s.id);
      extra.push({ id: s.id, name: s.name, present: true });
    }
    return [...base, ...extra];
  }, [snapshot?.cast, world, chat.speakers]);

  const speakerIndex = useSpeakers({
    cast,
    present: snapshot?.scene?.present,
    relations: snapshot?.relations,
    messages: chat.messages,
  });

  const scene = snapshot?.scene;
  const sceneLocation = scene?.location || session?.scene.location || world?.setting?.locations?.[0] || '';
  const sceneTime = scene?.time || session?.scene.time || '';
  const sceneMood = scene?.mood || session?.scene.mood || '';

  const archived = session?.status === 'archived';
  const disabledReason = archived
    ? '这一场剧情已归档。想继续这个故事，从世界观页重新开一场。'
    : usedDemoFallback
      ? '这是演示数据，接上后端即可真正开局。'
      : undefined;

  const handleSend = useCallback(
    (text: string) => {
      if (offline) {
        toast.show('演示模式下不会真的发给模型', '接上后端后，导演会安排角色依次回应。');
      }
      chat.send(text);
    },
    [offline, chat],
  );

  /* ---------------------------------------------------- 渲染 */

  if (!session) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <ErrorState
          description={`没找到这场剧情（id: ${id}）。它可能已被删除，或当前后端实例换了数据库。`}
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link to="/sessions">回到会话列表</Link>
              </Button>
              <Button variant="ghost" asChild>
                <Link to="/worlds">去剧情世界挑一个开局</Link>
              </Button>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex h-dvh flex-col bg-bg">
      {/* 顶部条 */}
      {!immersive ? (
        <div className="flex items-center gap-2 border-b border-border-soft bg-surface-sunken px-3 py-1.5">
          <Button variant="ghost" size="sm" asChild className="shrink-0">
            <Link to="/sessions">
              <ArrowLeft className="size-4" aria-hidden="true" />
              会话
            </Link>
          </Button>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-medium text-fg">
                {world?.title || '剧情演出'}
              </span>
              {sceneLocation ? <Badge variant="outline">{sceneLocation}</Badge> : null}
              {sceneTime ? <span className="tech-meta">{sceneTime}</span> : null}
              {sceneMood ? <span className="truncate text-xs text-muted">{sceneMood}</span> : null}
              {usedDemoFallback ? <Badge variant="warn">演示数据（未找到该剧情）</Badge> : null}
              {offline && !usedDemoFallback ? <Badge variant="warn">演示数据</Badge> : null}
              {snapshot?.story?.turn ? (
                <span className="tech-meta">第 {String(snapshot.story.turn)} 轮</span>
              ) : null}
              {chat.lastDecision?.degraded ? <Badge variant="warn">导演降级</Badge> : null}
            </div>
          </div>

          <DirectorCue decision={chat.lastDecision} onOpen={() => setDirectorOpen(true)} />
          <Button
            variant="ghost"
            size="sm"
            className="shrink-0"
            onClick={() => setImmersive(true)}
            aria-label="进入沉浸模式"
          >
            <Minimize2 className="size-4" aria-hidden="true" />
          </Button>
        </div>
      ) : (
        <div className="flex justify-end p-2">
          <Button variant="ghost" size="sm" onClick={() => setImmersive(false)} aria-label="退出沉浸模式">
            <Minimize2 className="size-4" aria-hidden="true" />
            退出沉浸
          </Button>
        </div>
      )}

      {!immersive ? <CastStrip speakers={speakerIndex} activeSpeakerId={chat.activeSpeaker?.id} /> : null}

      {!immersive && chat.nodes.length > 0 ? <NodeBanner nodes={chat.nodes} /> : null}

      {offline ? (
        <OfflineBanner>
          接不上后端，这里是演示数据。真实链路下导演会先给裁决、再让角色依次开口、最后给行动建议。
        </OfflineBanner>
      ) : null}

      <StoryReadingColumn
        messages={chat.messages}
        state={chat.state}
        generating={chat.generating}
        error={chat.error}
        speakers={speakerIndex}
        snapshot={snapshot}
        world={world}
        onRegenerate={
          offline
            ? undefined
            : (messageId) => {
                toast.show('正在重演这一条', '导演会重新安排一次这一拍。');
                chat.regenerate(messageId);
              }
        }
        onRetry={chat.retry}
      />

      <div className={cn('transition-opacity duration-[var(--dur-moderate)]', immersive && 'opacity-80 hover:opacity-100')}>
        <ActionDock
          suggestions={chat.suggestions}
          onSend={handleSend}
          onStop={chat.stop}
          generating={chat.generating}
          disabled={archived || usedDemoFallback}
          disabledReason={disabledReason}
          error={chat.error}
          onRetry={chat.retry}
        />
      </div>

      <DirectorPanel
        open={directorOpen}
        onOpenChange={setDirectorOpen}
        decision={chat.lastDecision}
        snapshot={snapshot}
        cast={cast}
      />

      {/* 快照拉取失败时的轻提示：不阻断游玩，只说明「场景信息可能不是最新的」 */}
      {storyQuery.isError && !offline ? (
        <div className="flex items-center justify-center gap-2 border-t border-border-soft bg-surface-sunken px-3 py-1.5">
          <span className="text-xs text-meta">剧情快照没读到，场景信息可能不是最新的。</span>
          <Button variant="ghost" size="sm" onClick={() => void storyQuery.refetch()}>
            <RefreshCw className="size-3.5" aria-hidden="true" />
            重读
          </Button>
        </div>
      ) : null}

      {/* 沉浸模式下的悬浮入口：不能因为隐藏 chrome 就丢掉导演面板 */}
      {immersive ? (
        <div className="pointer-events-none fixed bottom-24 right-4 z-drawer">
          <Button
            variant="secondary"
            size="icon"
            className="pointer-events-auto shadow-lg"
            aria-label="打开导演面板"
            onClick={() => setDirectorOpen(true)}
          >
            <Compass className="size-4" aria-hidden="true" />
          </Button>
        </div>
      ) : null}
    </div>
  );
}
