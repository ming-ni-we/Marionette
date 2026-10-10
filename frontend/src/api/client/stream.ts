/**
 * SSE 流式消费 —— POST /sessions/{id}/stream 为 text/event-stream。
 * EventSource 不支持 POST，故用 fetch + ReadableStream 手动解析 SSE 帧。
 */
import type { SseEventMap, SseEventName } from '../types';
import { ApiError, buildUrl, notifyUnauthorized, parseError } from './core';

export interface StreamCallbacks {
  onEvent: <K extends SseEventName>(event: K, data: SseEventMap[K]) => void;
  onError: (err: ApiError) => void;
  onClose: () => void;
}

/**
 * 消费 POST /sessions/{id}/stream 的 SSE 流。
 * 返回 abort() 用于中断（配合 POST /sessions/{id}/interrupt 保证无脏消息）。
 */
export function streamChat(
  sessionId: string,
  body: { input: string; idempotency_key?: string; overrides?: Record<string, unknown> },
  callbacks: StreamCallbacks,
): { abort: () => void } {
  const controller = new AbortController();

  const run = async () => {
    let res: Response;
    try {
      res = await fetch(buildUrl(`/sessions/${sessionId}/stream`), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        callbacks.onClose();
        return;
      }
      callbacks.onError(new ApiError(0, 0, '无法建立流式连接，请检查后端连通性', 'network_unreachable'));
      callbacks.onClose();
      return;
    }

    if (res.status === 401) {
      notifyUnauthorized();
      callbacks.onError(new ApiError(401, 4010, '访问会话已失效，请重新登录', 'auth_failed'));
      callbacks.onClose();
      return;
    }
    if (res.status === 409) {
      callbacks.onError(new ApiError(409, 4090, '当前会话正在生成中，请稍候', 'unknown'));
      callbacks.onClose();
      return;
    }
    if (!res.ok || !res.body) {
      callbacks.onError(await parseError(res));
      callbacks.onClose();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE 帧以空行分隔
        let sep = buffer.indexOf('\n\n');
        while (sep !== -1) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          dispatchFrame(frame, callbacks);
          sep = buffer.indexOf('\n\n');
        }
      }
      if (buffer.trim()) dispatchFrame(buffer, callbacks);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        callbacks.onError(new ApiError(0, 0, '流式连接中断，已生成内容保留', 'network_unreachable'));
      }
    } finally {
      callbacks.onClose();
    }
  };

  void run();
  return { abort: () => controller.abort() };
}

const KNOWN_EVENTS: SseEventName[] = [
  'world_info',
  'start',
  'delta',
  'usage',
  'image',
  'done',
  'error',
];

function dispatchFrame(frame: string, callbacks: StreamCallbacks): void {
  let eventName = 'message';
  const dataLines: string[] = [];
  for (const rawLine of frame.split('\n')) {
    const line = rawLine.replace(/\r$/, '');
    if (line.startsWith('event:')) eventName = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
    else if (line.startsWith(':')) {
      // 心跳注释，忽略
    }
  }
  if (dataLines.length === 0) return;
  const payload = dataLines.join('\n');
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    return;
  }
  if ((KNOWN_EVENTS as string[]).includes(eventName)) {
    callbacks.onEvent(eventName as SseEventName, parsed as SseEventMap[SseEventName]);
  }
}
