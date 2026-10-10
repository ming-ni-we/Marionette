import { useCallback, useRef, useState } from 'react';
import { makeIdempotencyKey } from '@/lib/utils';
import { sessionsApi, streamChat } from '@/api/client';
import type { Message, SessionState, SseEventMap, SseEventName } from '@/api/types';
import { mockStream } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';

interface UseChatStreamArgs {
  sessionId: string;
  /** 后端不可达 → 用本地 mockStream 走同一条事件链路 */
  offline: boolean;
}

export interface ChatStream {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  state: SessionState;
  setState: React.Dispatch<React.SetStateAction<SessionState>>;
  usage: { prompt_tokens: number; completion_tokens: number };
  setUsage: React.Dispatch<React.SetStateAction<{ prompt_tokens: number; completion_tokens: number }>>;
  worldInfoHits: number;
  setWorldInfoHits: React.Dispatch<React.SetStateAction<number>>;
  error: string | null;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  lastInput: string;
  setLastInput: React.Dispatch<React.SetStateAction<string>>;
  generating: boolean;
  send: (text: string, narration: string) => void;
  stop: () => void;
  retry: () => void;
  regenerateWith: (content: string) => void;
}

/**
 * 会话流式状态机（idle → assembling → generating → idle / error）。
 * 把 SSE 事件映射收敛在一处，页面只消费 messages/state/error。
 */
export function useChatStream({ sessionId, offline }: UseChatStreamArgs): ChatStream {
  const [messages, setMessages] = useState<Message[]>([]);
  const [state, setState] = useState<SessionState>('idle');
  const [usage, setUsage] = useState({ prompt_tokens: 0, completion_tokens: 0 });
  const [worldInfoHits, setWorldInfoHits] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [lastInput, setLastInput] = useState('');
  const handleRef = useRef<{ abort: () => void } | null>(null);

  const patchLastAssistant = useCallback((patch: Partial<Message>) => {
    setMessages((m) => {
      if (m.length === 0) return m;
      const next = [...m];
      const last = next[next.length - 1];
      if (last.role !== 'assistant') return m;
      next[next.length - 1] = { ...last, ...patch };
      return next;
    });
  }, []);

  const onSse = useCallback(
    (event: SseEventName, raw: SseEventMap[SseEventName]) => {
      const data = raw as unknown as Record<string, unknown>;
      switch (event) {
        case 'world_info': {
          const triggered = (data.triggered as Array<{ in_budget: boolean }>) ?? [];
          setWorldInfoHits((n) => n + triggered.filter((t) => t.in_budget).length);
          break;
        }
        case 'start':
          setState('generating');
          break;
        case 'delta':
          // 仅追加文本；布局高度由内容自然增长（不做 height 动画，避免抖动）
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last?.role === 'assistant') {
              next[next.length - 1] = { ...last, content: last.content + String(data.text ?? '') };
            }
            return next;
          });
          break;
        case 'usage':
          setUsage({
            prompt_tokens: Number(data.prompt_tokens ?? 0),
            completion_tokens: Number(data.completion_tokens ?? 0),
          });
          break;
        case 'image':
          toast.show('场景图已生成并归档', '可以在「素材」里按角色找到它。');
          break;
        case 'done':
          patchLastAssistant({ status: String(data.status) === 'complete' ? 'complete' : 'incomplete' });
          setState('idle');
          break;
        case 'error':
          setError(String(data.message ?? '生成失败'));
          patchLastAssistant({ status: 'incomplete' });
          setState('error');
          break;
        default:
          break;
      }
    },
    [patchLastAssistant],
  );

  const startStream = useCallback(
    (input: string) => {
      setState('assembling');
      setError(null);
      setMessages((m) => [
        ...m,
        {
          id: `local-assistant-${Date.now()}`,
          role: 'assistant',
          content: '',
          status: 'streaming',
          token_count: 0,
          created_at: new Date().toISOString(),
        },
      ]);

      if (offline) {
        handleRef.current = mockStream(
          (event, data) => onSse(event as SseEventName, data as unknown as SseEventMap[SseEventName]),
          () => undefined,
        );
        return;
      }
      handleRef.current = streamChat(
        sessionId,
        { input, idempotency_key: makeIdempotencyKey() },
        {
          onEvent: onSse,
          onError: (err) => {
            setError(err.message);
            patchLastAssistant({ status: 'incomplete' });
            setState('error');
          },
          onClose: () => setState((s) => (s === 'error' ? s : 'idle')),
        },
      );
    },
    [sessionId, offline, onSse, patchLastAssistant],
  );

  const send = useCallback(
    (text: string, narration: string) => {
      const content = narration ? `${text}\n\n（旁白：${narration}）` : text;
      setMessages((m) => [
        ...m,
        {
          id: `local-user-${Date.now()}`,
          role: 'user',
          content,
          status: 'complete',
          token_count: 0,
          created_at: new Date().toISOString(),
        },
      ]);
      setLastInput(text);
      startStream(content);
    },
    [startStream],
  );

  const stop = useCallback(() => {
    handleRef.current?.abort();
    handleRef.current = null;
    patchLastAssistant({ status: 'incomplete' });
    setState('idle');
    if (!offline) void sessionsApi.interrupt(sessionId).catch(() => undefined);
  }, [sessionId, offline, patchLastAssistant]);

  const retry = useCallback(() => {
    // 去掉失败的空 assistant 占位，用同一句输入重跑
    setMessages((m) => {
      const next = [...m];
      if (next[next.length - 1]?.role === 'assistant' && !next[next.length - 1].content) next.pop();
      return next;
    });
    startStream(lastInput);
  }, [lastInput, startStream]);

  /** 用指定内容重新生成（阅读列里对某条消息点「重新生成」时用） */
  const regenerateWith = useCallback(
    (content: string) => {
      setLastInput(content);
      startStream(content);
    },
    [startStream],
  );

  return {
    messages,
    setMessages,
    state,
    setState,
    usage,
    setUsage,
    worldInfoHits,
    setWorldInfoHits,
    error,
    setError,
    lastInput,
    setLastInput,
    generating: state === 'generating' || state === 'assembling',
    send,
    stop,
    retry,
    regenerateWith,
  };
}
