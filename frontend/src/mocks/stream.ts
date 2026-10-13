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

/**
 * 剧情模式事件链路的本地模拟：`world_info → director → start → (旁白 | 角色轮演) → node? → usage → actions → done`。
 *
 * **为什么必须复刻后端那些「不对称」的细节**：真实后端对**第一个**说话者
 * 不发 `speaker_switch`（见 `backend/app/services/chat.py` 的 `if index > 0:`），
 * 只发 `delta + speaker_id`；旁白则相反——一次性落库、**完全不走 delta**。
 * 如果 mock 图省事给每个说话者都发 `speaker_switch`，那么
 * 「首个说话者的正文被串进旁白气泡」这类真实 bug 在离线路径上永远不会暴露，
 * 演示一切正常、上线立刻出错。所以这里刻意与后端保持同构。
 */
export function mockStoryStream(
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

  const NARRATION =
    '雨下了三天。旧城区的墙皮泡得发胀，像随时会掉下来一层。\n柜台后面有人在翻一本旧账，纸张翻动的声音比雨声还轻。';

  /** [speaker_id, 名字, 分段台词] —— 镜像后端一轮多角色的真实形态 */
  const beats: Array<[string, string, string[]]> = [
    ['c1', '苏晚', ['她没抬头，把账本往阴影里推了半寸。\n\n', '「雨大，伞搁门口就行。」']],
    ['c2', '老周', ['「苏晚！」\n\n', '老周的声音先于人进了门，带着一股湿透的烟味。\n\n', '「公告你看了没有？」']],
  ];

  push(
    () =>
      onEvent('world_info', {
        triggered: [{ entry_id: 'e-0002', match_type: 'keyword', in_budget: true }],
        trace_id: 'demo-story',
      }),
    100,
  );

  // director：先发裁决，让前端立刻能渲染透明性面板
  push(
    () =>
      onEvent('director', {
        speakers: [
          { id: 'c1', name: '苏晚', intent: '不愿接话，先试探对方来意', direction: '话少，句子短' },
          { id: 'c2', name: '老周', intent: '把压力转嫁给在场所有人', direction: '嗓门大，爱用旧事压人' },
        ],
        narration: NARRATION,
        scene_patch: { mood: '压抑' },
        node_triggered: {
          id: 'n1',
          title: '雨夜的第一封信',
          brief: '苏晚在书店夹墙里发现一封没寄出的信，收信人是她自己。',
        },
        relation_updates: [{ from: 'c2', to: 'c3', kind: '宿敌', tension: -0.8 }],
        flags: { 公告已贴出: true },
        reason:
          '玩家刚进门且未表明立场，先把两位对拆迁态度最对立的人摆上台，让矛盾自己浮现；苏晚打头制造沉默，再由老周打破。',
        degraded: false,
      }),
    220,
  );

  push(() => onEvent('start', { message_id: '', estimated_prompt_tokens: 2140 }), 300);

  // 旁白：真实后端一次性落库、只发 speaker_switch（带 message_id）后**不再走 delta**，
  // 正文由下一次 GET /sessions/{id} 回读。离线模式没有数据库可回读，
  // 所以这里额外补若干 `delta`（speaker_id: null）把正文推给前端 —— 
  // 这是**离线专属**的补丁，用来让演示页能看到旁白；真实链路不依赖它。
  push(
    () =>
      onEvent('speaker_switch', {
        speaker_id: null,
        speaker_name: '',
        is_narration: true,
        message_id: 'demo-narration',
      }),
    360,
  );

  let tn = 390;
  for (const piece of [NARRATION.slice(0, 22), NARRATION.slice(22)]) {
    push(() => onEvent('delta', { text: piece, speaker_id: null }), tn);
    tn += 180;
  }

  let t = 420;
  beats.forEach(([id, name, chunks], index) => {
    // 注意：只对 index > 0 发 speaker_switch —— 与后端完全一致。
    // 首个说话者后端刻意不发该事件，只发 delta + speaker_id；
    // mock 若这里「补全」，G1 那类串行 bug 在离线路径上就永远测不出来。
    if (index > 0) {
      push(() => onEvent('speaker_switch', { speaker_id: id, speaker_name: name, is_narration: false }), t);
      t += 60;
    }
    for (const chunk of chunks) {
      push(() => onEvent('delta', { text: chunk, speaker_id: id }), t);
      t += 420;
    }
    t += 120;
  });

  push(
    () =>
      onEvent('node', {
        id: 'n1',
        title: '雨夜的第一封信',
        brief: '苏晚在书店夹墙里发现一封没寄出的信，收信人是她自己。',
      }),
    t,
  );
  push(() => onEvent('usage', { prompt_tokens: 2140, completion_tokens: 268 }), t + 100);
  push(
    () =>
      onEvent('actions', {
        actions: [
          { id: 'a1', label: '把伞立到门边，先不说话', hint: '看看谁会先开口', tone: 'observe' },
          { id: 'a2', label: '问苏晚那本账是谁的', hint: '直指她藏起来的东西', tone: 'speak' },
          { id: 'a3', label: '帮老周把门带上', hint: '站到某一边去', tone: 'act' },
          { id: 'a4', label: '走到夹墙那边看看', hint: '离开柜台前的对峙', tone: 'move' },
        ],
      }),
    t + 180,
  );
  push(() => {
    onEvent('done', { message_id: 'demo-speaker-last', status: 'complete', turn: 2 });
    onClose();
  }, t + 280);

  return {
    abort: () => {
      cancelled = true;
      for (const id of timers) window.clearTimeout(id);
      onEvent('done', { message_id: '', status: 'incomplete' });
      onClose();
    },
  };
}
