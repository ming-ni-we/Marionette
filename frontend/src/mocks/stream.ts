/**
 * 会话流式事件本地模拟（后端不可达时使用）。
 * 复刻真实 SSE 链路：world_info → start → delta* → usage → done（支持中断）。
 */
import type { SessionState } from '@/api/types';

/** 会话状态机的中文标签（UI 状态条使用，禁止 emoji）。 */
export const STATE_LABEL: Record<SessionState, string> = {
  idle: '空闲',
  assembling: '装配上下文',
  generating: '生成中',
  post_processing: '后处理',
  interrupted: '已中断',
  error: '出错',
};

export interface MockStreamHandle {
  abort: () => void;
}

export function mockStream(
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onClose: () => void,
): MockStreamHandle {
  const timers: number[] = [];
  let cancelled = false;
  const push = (fn: () => void, delay: number) => {
    timers.push(
      window.setTimeout(() => {
        if (!cancelled) fn();
      }, delay),
    );
  };

  const reply = [
    '她没接话，先把唱机的针头放下去。',
    '邓丽君的声音从喇叭里挤出来，带着一点电流的沙。\n\n',
    '「雨要下到后半夜。」她看着窗外，「你要是不急着走——',
    '那杯茶还能续。」\n\n',
    '她转身去拿水壶，围裙口袋里的怀表轻轻磕了一下柜台。',
  ];

  push(
    () =>
      onEvent('world_info', {
        triggered: [{ entry_id: 'e-0002', match_type: 'keyword', in_budget: true }],
        trace_id: 'demo',
      }),
    120,
  );
  push(() => onEvent('start', { message_id: 'demo-msg', estimated_prompt_tokens: 1582 }), 260);

  let t = 420;
  for (const chunk of reply) {
    push(() => onEvent('delta', { text: chunk }), t);
    t += 480;
  }
  push(() => onEvent('usage', { prompt_tokens: 1582, completion_tokens: 96 }), t);
  push(() => {
    onEvent('done', { message_id: 'demo-msg', status: 'complete' });
    onClose();
  }, t + 200);

  return {
    abort: () => {
      cancelled = true;
      for (const id of timers) window.clearTimeout(id);
      onEvent('done', { message_id: 'demo-msg', status: 'incomplete' });
      onClose();
    },
  };
}
