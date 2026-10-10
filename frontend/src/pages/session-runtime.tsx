import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { sessionsApi } from '@/api/client';
import type { ContextSnapshot } from '@/api/types';
import { SAMPLE_CONTEXT, SAMPLE_SESSIONS } from '@/mocks/fixtures';
import { toast, useUiStore } from '@/stores/ui';
import { useChatStream } from '@/hooks/use-chat-stream';
import { IndicatorStrip } from '@/components/session/indicator-strip';
import { ReadingColumn } from '@/components/session/reading-column';
import { SceneBar } from '@/components/session/scene-bar';
import { Composer } from '@/components/session/composer';
import { SessionDrawer } from '@/components/session/session-drawer';
import { ErrorState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import { Minimize2, ArrowLeft } from '@/components/icons';

/** 会话运行时（SPEC §7.4/§7.5）：68ch 单列 · 沉浸模式 · 指示条 · 抽屉 · SSE 状态机 */
export function SessionRuntimePage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const setDensity = useUiStore((s) => s.setDensity);
  const immersive = useUiStore((s) => s.immersive);
  const setImmersive = useUiStore((s) => s.setImmersive);
  const drawer = useUiStore((s) => s.sessionDrawer);
  const setDrawer = useUiStore((s) => s.setSessionDrawer);

  const query = useQuery({
    queryKey: ['session', id],
    queryFn: () => sessionsApi.get(id),
    retry: false,
  });

  const demoSession = SAMPLE_SESSIONS.find((s) => s.id === id);
  const offline = query.isError;
  const session = query.data ?? (offline ? demoSession ?? SAMPLE_SESSIONS[0] : undefined);
  const usedDemoFallback = offline && !demoSession;

  const chat = useChatStream({ sessionId: id, offline });
  const [snapshot, setSnapshot] = useState<ContextSnapshot | null>(null);
  const seededRef = useRef<string | null>(null);

  const { setMessages, setWorldInfoHits, setUsage, setError, setState } = chat;

  // 运行端切到 session 密度；离开恢复 studio
  useEffect(() => {
    setDensity('session');
    return () => setDensity('studio');
  }, [setDensity]);

  useEffect(() => {
    if (session && seededRef.current !== session.id) {
      setMessages(session.messages);
      setWorldInfoHits(Object.keys(session.triggered_entries).length);
      setUsage({ prompt_tokens: 0, completion_tokens: 0 });
      setSnapshot(null);
      setError(null);
      setState('idle');
      seededRef.current = session.id;
    }
  }, [session, setMessages, setWorldInfoHits, setUsage, setError, setState]);

  // 沉浸模式 Esc 退出
  useEffect(() => {
    if (!immersive) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setImmersive(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [immersive, setImmersive]);

  const loadSnapshot = useCallback(() => {
    if (offline) {
      setSnapshot(SAMPLE_CONTEXT);
      return;
    }
    sessionsApi
      .lastContext(id)
      .then(setSnapshot)
      .catch(() => toast.danger('读取失败', '这一轮可能还没生成完成。'));
  }, [id, offline]);

  const forkMutation = useMutation({
    mutationFn: (messageId: string) => sessionsApi.fork(id, { from_message_id: messageId }),
    onSuccess: (s) => {
      toast.success('已从该节点分叉', '原会话保持不变。');
      void qc.invalidateQueries({ queryKey: ['sessions'] });
      navigate(`/sessions/${s.id}`);
    },
    onError: () => toast.danger('分叉失败', '后端拒绝了这次请求。'),
  });

  const handleFork = useCallback(
    (messageId: string) => {
      if (offline) {
        toast.show('演示模式下不能真的分叉', '接上后端后这里会创建一条独立分支会话。');
        return;
      }
      forkMutation.mutate(messageId);
    },
    [offline, forkMutation],
  );

  const speakerName = useMemo(() => {
    const cardId = session?.character_card_id;
    if (!cardId) return '角色';
    return cardId === SAMPLE_SESSIONS[0].character_card_id ? '苏晚' : '角色';
  }, [session]);

  const maxTokens = snapshot?.budget.max_context_tokens ?? 8192;
  const usedTokens = snapshot?.budget.used_tokens ?? chat.usage.prompt_tokens;

  if (!session) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <ErrorState
          description={`没找到这场会话（id: ${id}）。它可能已被删除，或当前后端实例换了数据库。`}
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link to="/sessions">回到会话列表</Link>
              </Button>
              <Button variant="ghost" asChild>
                <Link to="/">去内容库挑一张卡开会话</Link>
              </Button>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex h-dvh flex-col bg-bg">
      {/* 顶部细指示条（沉浸模式下隐藏，只留正文） */}
      {!immersive ? (
        <div className="flex items-center gap-2 border-b border-border-soft bg-surface-sunken px-3">
          <Button variant="ghost" size="sm" asChild className="shrink-0">
            <Link to="/sessions">
              <ArrowLeft className="size-4" aria-hidden="true" />
              会话
            </Link>
          </Button>
          <div className="min-w-0 flex-1">
            <IndicatorStrip
              className="border-b-0 bg-transparent px-0"
              worldInfoHits={chat.worldInfoHits}
              memoryFactCount={session.memory.facts.length}
              usedTokens={usedTokens}
              maxTokens={maxTokens}
              branchCount={chat.messages.length}
              state={chat.state}
              onOpenContext={() => setDrawer('context')}
              onOpenTree={() => setDrawer('tree')}
              onEnterImmersive={() => setImmersive(true)}
            />
          </div>
        </div>
      ) : (
        <div className="flex justify-end p-2">
          <Button variant="ghost" size="sm" onClick={() => setImmersive(false)} aria-label="退出沉浸模式">
            <Minimize2 className="size-4" aria-hidden="true" />
            退出沉浸
          </Button>
        </div>
      )}

      {!immersive ? (
        <SceneBar session={session} offline={offline} usedDemoFallback={usedDemoFallback} />
      ) : null}

      <ReadingColumn
        messages={chat.messages}
        speakerName={speakerName}
        state={chat.state}
        generating={chat.generating}
        error={chat.error}
        hasOpening={Boolean((session.messages[0]?.content ?? '').trim())}
        onRegenerate={(m) => chat.regenerateWith(m.content)}
        onFork={handleFork}
        onRetry={chat.retry}
      />

      {/* 输入区 */}
      <div className={cn('transition-opacity duration-[var(--dur-moderate)]', immersive && 'opacity-80 hover:opacity-100')}>
        <Composer
          onSend={chat.send}
          onStop={chat.stop}
          generating={chat.generating}
          disabledReason={
            session.status === 'archived' ? '这场会话已归档。要接着聊，先新建一场或从某条消息分叉。' : undefined
          }
        />
      </div>

      {/* 右侧抽屉：上下文检视 / 分支树 */}
      <SessionDrawer
        open={drawer !== 'none'}
        tab={drawer === 'tree' ? 'tree' : 'context'}
        onTabChange={(t) => setDrawer(t)}
        onOpenChange={(open) => setDrawer(open ? 'context' : 'none')}
        snapshot={snapshot}
        snapshotLoading={false}
        onLoadSnapshot={loadSnapshot}
        messages={chat.messages}
        currentMessageId={chat.messages[chat.messages.length - 1]?.id}
        onFork={handleFork}
        onJump={() => setDrawer('none')}
      />
    </div>
  );
}
