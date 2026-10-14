import { useCallback, useRef, useState } from 'react';import { makeIdempotencyKey } from '@/lib/utils';
import { regenerateChat, sessionsApi, streamChat } from '@/api/client';
import type {
  ActionSuggestion,
  CastMember,
  Message,
  Relation,
  SessionState,
  SseDirectorEvent,
  SseEventMap,
  SseEventName,
  StoryState,
} from '@/api/types';
import { mockStream, mockStoryStream } from '@/mocks/fixtures';
import { toast } from '@/stores/ui';

interface UseChatStreamArgs {
  sessionId: string;
  /** 后端不可达 → 用本地 mockStream 走同一条事件链路 */
  offline: boolean;
  /**
   * 剧情模式（`spec === 'story_session'`）。
   *
   * 打开它会改变两个行为，都是为了对齐后端「N 个说话者 = N 条消息」的契约：
   *   1) `startStream` **不预建空占位**——剧情的消息行由后端在演出循环里建，
   *      前端预建会多出一条永远填不满的空气泡
   *   2) `done` 时**清掉仍然为空的占位**——包括中途中断留下的
   * 1v1 保持原行为（需要那条占位来承接首个 `delta`）。
   */
  storyMode?: boolean;
}

/** 本轮里正在说的那个人（由 `speaker_switch` 驱动）。 */
export interface ActiveSpeaker {
  id: string | null;
  name: string;
  isNarration: boolean;
  /** 该说话者消息行 id（后端新建时给出；旁白也有） */
  messageId: string;
}

/** 剧情配图（S16-8）：流式期间由 `image` 事件累积，回读时走 `message.meta`。 */
export interface SceneImage {
  assetId: string;
  reason: 'cast' | 'node' | 'manual';
  /** 挂载锚点：这条图属于哪条 assistant 消息 */
  messageId: string;
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
  /* ---------------------------------------------- 剧情模式（1v1 下恒为空） */
  /** 本轮导演排出的出场角色（`director` 事件） */
  speakers: CastMember[];
  /** 当前正在说话的人（`speaker_switch` 事件） */
  activeSpeaker: ActiveSpeaker | null;
  /** 本轮已触发的剧情节点（`node` 事件） */
  nodes: SseEventMap['node'][];
  /** 最近一轮的行动建议（`actions` 事件） */
  suggestions: ActionSuggestion[];
  /**
   * 本轮已生成的剧情配图（`image` 事件，S16-8）。
   *
   * 与 `message.meta.image_asset_id`（回读）合并后渲染 —— 两条路径共用一个
   * `messageId` 锚点，所以无论「刚生成」还是「刷新后回读」，图都落在同一条消息下。
   */
  sceneImages: SceneImage[];
  /** 最近一次导演裁决原文（供调试面板展示「导演在想什么」） */
  lastDecision: SseDirectorEvent | null;
  setSuggestions: React.Dispatch<React.SetStateAction<ActionSuggestion[]>>;
  setActiveSpeaker: React.Dispatch<React.SetStateAction<ActiveSpeaker | null>>;
  /** 外部把 /story 快照灌进来（首次进页面时用） */
  setStorySnapshot: (
    snap: {
      story?: StoryState;
      relations?: Relation[];
      cast?: CastMember[];
      /** 上一轮落库的行动建议（S15-1）—— 刷新/重开会话时恢复芯片区 */
      suggestions?: ActionSuggestion[];
    } | null,
  ) => void;
  /**
   * 发送一轮输入。
   * `narration` 保持**可选第二参**：1v1 的 Composer 会传「旁白/指令」，
   * 剧情模式的 ActionDock 只传正文。合并成一个签名，两套 UI 共用同一 hook。
   */
  send: (text: string, narration?: string) => void;
  stop: () => void;
  retry: () => void;
  regenerate: (messageId: string) => void;
}

/**
 * 会话流式状态机（idle → assembling → generating → idle / error）。
 * 把 SSE 事件映射收敛在一处，页面只消费 messages/state/error。
 */
export function useChatStream({ sessionId, offline, storyMode = false }: UseChatStreamArgs): ChatStream {
  const [messages, setMessages] = useState<Message[]>([]);
  const [state, setState] = useState<SessionState>('idle');
  const [usage, setUsage] = useState({ prompt_tokens: 0, completion_tokens: 0 });
  const [worldInfoHits, setWorldInfoHits] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [lastInput, setLastInput] = useState('');
  // 剧情模式状态（1v1 恒为空/空数组，不产生额外渲染开销）
  const [speakers, setSpeakers] = useState<CastMember[]>([]);
  const [activeSpeaker, setActiveSpeaker] = useState<ActiveSpeaker | null>(null);
  const [nodes, setNodes] = useState<SseEventMap['node'][]>([]);
  const [suggestions, setSuggestions] = useState<ActionSuggestion[]>([]);
  const [sceneImages, setSceneImages] = useState<SceneImage[]>([]);
  const [lastDecision, setLastDecision] = useState<SseDirectorEvent | null>(null);
  const handleRef = useRef<{ abort: () => void } | null>(null);

  /**
   * 当前说话者的镜像 ref。
   * `appendDelta` 需要它，但 `appendDelta` 不能把 `activeSpeaker` 放进依赖
   * （否则每轮每次切换都会重建回调、连带重建整个 `onSse`）。用 ref 读最新值，
   * 让 `appendDelta` 保持空依赖、引用稳定。
   */
  const activeSpeakerRef = useRef<ActiveSpeaker | null>(null);

  /**
   * 本轮标识 —— 每轮开演时换一个新值，并给本轮产生的每条气泡打上它。
   *
   * **用途**：`appendDelta` 靠 `speaker_id` 反查"该写进哪条气泡"。
   * 若不加范围限制，反查会命中**上一轮**同角色的气泡（同一角色每轮 id 相同），
   * 于是本轮回复被写到用户消息上方的历史气泡里 —— 表现就是
   * "我回答完，角色的话跑到我上面去了"。
   *
   * 所以反查只在「本轮」范围内进行：本轮没有对应气泡时**就地新建**，
   * 保证回复永远出现在用户消息**下方**。
   */
  const turnKeyRef = useRef<string>('');

  /** 打上本轮标记（新对象，避免污染既有引用）。 */
  const tagTurn = <T extends { meta?: Message['meta'] }>(msg: T): T => ({
    ...msg,
    meta: { ...(msg.meta ?? {}), _turnKey: turnKeyRef.current },
  });

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

  /**
   * 按 `speaker_id` 精确落点。
   *
   * 剧情模式一轮有多条气泡，而 `delta` 只带 `speaker_id`、不带消息 id，
   * 因此需要靠 `speaker_id` 反查当前正在写的那条。
   *
   * **两条铁律**：
   *
   * 1. **只在「本轮」范围内反查** —— 反查条件带上 `_turnKey === turnKeyRef.current`。
   *    同一角色每轮都在场、`speaker_id` 不变，若不限定范围就会命中上一轮的旧气泡，
   *    本轮回复被追加到用户消息**上方**（历史位置），看起来"角色插话到我的问题前面去了"。
   *
   * 2. **找不到时必须就地新建，不能退回「最后一条」** ——
   *    后端出于「N 个说话者 = N 条消息」的考虑，对**第一个**说话者
   *    不发 `speaker_switch`（见 `chat.py` 的 `if index > 0:`），只发 `delta + speaker_id`。
   *    若此时退回「最后一条 assistant」，该说话者的正文会被追加进
   *    前一条消息——通常是导演的旁白——于是旁白气泡里长出角色台词。
   *    1v1 无 `speaker_id`（undefined）时才走退回分支。
   */
  const appendDelta = useCallback((text: string, speakerId?: string | null) => {
    if (!text) return;
    setMessages((m) => {
      if (m.length === 0) return m;
      const next = [...m];

      /* ---- 1v1：无 speaker_id → 沿用「最后一条 assistant」 ---- */
      if (speakerId === undefined) {
        const last = next[next.length - 1];
        if (last?.role !== 'assistant') return m;
        next[next.length - 1] = { ...last, content: last.content + text };
        return next;
      }

      /* ---- 剧情模式：speaker_id 为 null 表示旁白（后端把旁白也归到这条通道） ---- */
      if (speakerId === null) {
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].meta?.is_narration && next[i].meta?._turnKey === turnKeyRef.current) {
            next[i] = { ...next[i], content: next[i].content + text, status: 'streaming' };
            return next;
          }
        }
      }

      /* ---- 剧情模式：按 speaker_id 反查（限本轮，从后往前，避免误命中历史气泡） ---- */
      for (let i = next.length - 1; i >= 0; i -= 1) {
        if (
          next[i].meta?.speaker_id === speakerId &&
          next[i].meta?._turnKey === turnKeyRef.current
        ) {
          next[i] = { ...next[i], content: next[i].content + text };
          return next;
        }
      }

      /* ---- 本轮该说话者还没有气泡 → 就地新建（首个说话者走这条路）---- */
      const lastName =
        activeSpeakerRef.current?.id === speakerId ? activeSpeakerRef.current.name : '';
      next.push(
        tagTurn({
          id: `local-speaker-${Date.now()}-${next.length}`,
          role: 'assistant' as const,
          content: text,
          status: 'streaming' as const,
          token_count: 0,
          created_at: new Date().toISOString(),
          meta: {
            speaker_id: speakerId,
            speaker_name: lastName || null,
            is_narration: false,
            beat_role: 'reply' as const,
          },
        }),
      );
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
          appendDelta(String(data.text ?? ''), 'speaker_id' in data ? (data.speaker_id as string | null) : undefined);
          break;
        /* -------------------------------------------- 剧情模式 4 个新事件 */
        case 'director': {
          const d = raw as SseEventMap['director'];
          setLastDecision(d);
          setSpeakers((d.speakers ?? []) as CastMember[]);
          // 导演是每轮第一件事：清掉上一轮残留，避免新旧建议/节点/配图串轮
          setNodes([]);
          setSuggestions([]);
          setSceneImages([]);
          setActiveSpeaker(null);
          break;
        }
        case 'speaker_switch': {
          const s = raw as SseEventMap['speaker_switch'];
          const next: ActiveSpeaker = {
            id: s.speaker_id ?? null,
            name: s.speaker_name ?? '',
            isNarration: Boolean(s.is_narration),
            messageId: s.message_id ?? '',
          };
          setActiveSpeaker(next);
          activeSpeakerRef.current = next;

          // 按后端给的 id 做 upsert。
          // - 带 `message_id`（旁白）：后端已把那行落库，但它在**本轮**才创建，
          //   而本地 messages 是首屏 `GET /sessions/{id}` 播种的旧快照 —— 里面没有它。
          //   所以不能假设「后端有 = 本地有」，必须补一条带真实 id 的占位，
          //   否则旁白在整轮里都不会显示（历史 bug）。
          // - 不带 `message_id`（第 2 个及以后的说话者）：同样补占位承接后续 delta。
          // - 首个说话者后端连 switch 都不发，由 appendDelta 就地新建。
          const localId = next.messageId || `local-speaker-${Date.now()}-${s.speaker_id ?? 'n'}`;
          setMessages((m) => {
            if (m.some((x) => x.id === localId)) return m;
            // 旁白行后端已是 complete 且正文完整；这里不能标成 streaming，
            // 否则 done 之前它会被误判成「还在生成」。
            const narrationDone = next.isNarration && Boolean(next.messageId);
            return [
              ...m,
              tagTurn({
                id: localId,
                role: 'assistant' as const,
                content: '',
                status: narrationDone ? ('complete' as const) : ('streaming' as const),
                token_count: 0,
                created_at: new Date().toISOString(),
                meta: {
                  speaker_id: next.id,
                  speaker_name: next.name || null,
                  is_narration: next.isNarration,
                  beat_role: next.isNarration ? ('narration' as const) : ('reply' as const),
                },
              }),
            ];
          });
          break;
        }
        case 'node': {
          setNodes((n) => [...n, raw as SseEventMap['node']]);
          break;
        }
        case 'actions': {
          setSuggestions((raw as SseEventMap['actions']).actions ?? []);
          break;
        }
        case 'usage':
          setUsage({
            prompt_tokens: Number(data.prompt_tokens ?? 0),
            completion_tokens: Number(data.completion_tokens ?? 0),
          });
          break;
        case 'image': {
          // 剧情配图（S16-8）：记下 asset_id 与挂载锚点，交给渲染层插进对话流。
          // 同 messageId 覆盖而非追加 —— 单轮最多一图，重复事件不该画出两张。
          const im = raw as SseEventMap['image'];
          const scene: SceneImage = {
            assetId: im.asset_id,
            reason: im.reason ?? 'node',
            messageId: im.message_id ?? '',
          };
          setSceneImages((arr) => [...arr.filter((x) => x.messageId !== scene.messageId), scene]);
          toast.show('场景图已生成并归档', '已加入本幕。');
          break;
        }
        case 'done': {
          const status: Message['status'] = String(data.status) === 'complete' ? 'complete' : 'incomplete';
          // 剧情模式：本轮可能有多条气泡，把仍是 streaming 的全部收口
          setMessages((m) =>
            m
              .map((x) => (x.status === 'streaming' ? { ...x, status } : x))
              // 剧情模式清掉始终没写进内容的空气泡（中断 / 后端未建行时留下）
              .filter((x) => !(storyMode && x.role === 'assistant' && !x.content && !x.meta?.is_narration)),
          );
          setState('idle');
          setActiveSpeaker(null);
          activeSpeakerRef.current = null;
          break;
        }
        case 'error':
          setError(String(data.message ?? '生成失败'));
          patchLastAssistant({ status: 'incomplete' });
          setState('error');
          break;
        default:
          break;
      }
    },
    [patchLastAssistant, appendDelta, storyMode],
  );

  const startStream = useCallback(
    (input: string, opener?: (cb: Parameters<typeof streamChat>[2]) => { abort: () => void }) => {
      setState('assembling');
      setError(null);
      // 开新一轮：换 turnKey，让本轮气泡与历史气泡区分开。
      // 必须在这里（而不是 send 里）—— regenerate / retry 也走这条路。
      turnKeyRef.current = `t-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      // 剧情模式：消息行由后端在演出循环里创建（start.message_id 为空串），
      // 前端预建会多出一条填不满的空气泡 —— 见 UseChatStreamArgs.storyMode
      if (!storyMode) {
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
      }

      if (offline) {
        // 剧情模式的离线链路必须走剧情事件序列（含 director / speaker_switch / actions），
        // 否则演示页面永远看不到导演裁决与行动建议。
        const mock = storyMode ? mockStoryStream : mockStream;
        handleRef.current = mock(
          (event, data) => onSse(event as SseEventName, data as unknown as SseEventMap[SseEventName]),
          () => undefined,
        );
        return;
      }
      const callbacks = {
        onEvent: onSse,
        onError: (err: { message: string }) => {
          setError(err.message);
          patchLastAssistant({ status: 'incomplete' });
          setState('error');
        },
        onClose: () => setState((s) => (s === 'error' ? s : 'idle')),
      };
      handleRef.current = opener
        ? opener(callbacks)
        : streamChat(sessionId, { input, idempotency_key: makeIdempotencyKey() }, callbacks);
    },
    [sessionId, offline, storyMode, onSse, patchLastAssistant],
  );

  const send = useCallback(
    (text: string, narration = '') => {
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

  /** 把 GET /sessions/{id}/story 的快照灌进剧情态（首屏回填在场角色/关系/建议）。 */
  const setStorySnapshot = useCallback(
    (snap: {
      story?: StoryState;
      relations?: Relation[];
      cast?: CastMember[];
      suggestions?: ActionSuggestion[];
    } | null) => {
      if (!snap) return;
      if (snap.cast) setSpeakers(snap.cast);
      // S15-1：恢复上一轮建议。此前建议只活在 SSE 瞬态里，刷新即丢 ——
      // 玩家重开历史会话看到的永远是空建议区。这里只在快照**带上**该字段时回填，
      // 避免老会话（无此键）把原本已有的建议清空。
      if (snap.suggestions) setSuggestions(snap.suggestions);
    },
    [],
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

  /** 对指定消息走契约端点 POST /sessions/{id}/regenerate（缺省为最后一条）。 */
  const regenerate = useCallback(
    (messageId: string) => {
      startStream('', (cb) => regenerateChat(sessionId, { message_id: messageId }, cb));
    },
    [sessionId, startStream],
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
    speakers,
    activeSpeaker,
    nodes,
    suggestions,
    sceneImages,
    lastDecision,
    setSuggestions,
    setActiveSpeaker,
    setStorySnapshot,
    send,
    stop,
    retry,
    regenerate,
  };
}
