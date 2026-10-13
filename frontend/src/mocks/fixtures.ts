/**
 * 本地演示数据统一出口（barrel）。
 * -----------------------------------------------------------------------------
 * **仅在后端不可达时启用，UI 必须明确标注「演示数据」（见 `DEMO_FLAG`）。**
 * 用途：
 *   1) 让 AC-16「不得出现空白页」在离线状态下也有真实可读的内容
 *   2) 演示本产品差异化视觉点——世界书命中测试三态、会话流式事件链路
 * 原则：内容为真实可用的「现代日常向」示例，不使用 Lorem ipsum / John Doe / 虚构指标。
 *
 * 实现按用途拆分，避免单文件超长（SPEC §10）：
 *   - `./samples/*`  静态实体数据（卡 / 世界书 / 预设 / 会话）
 *   - `./system`     系统信息与演示标注
 *   - `./assets`     素材库
 *   - `./context`    上下文装配快照
 *   - `./worldbook-test`  世界书命中测试（三态）
 *   - `./stream`     SSE 事件链路模拟 + 状态标签
 * -----------------------------------------------------------------------------
 */
export { T0, T1 } from './samples/shared';
export { SAMPLE_CARDS } from './samples/cards';
export { SAMPLE_WORLDBOOKS } from './samples/worldbooks';
export { SAMPLE_PRESETS } from './samples/presets';
export { SAMPLE_SESSIONS } from './samples/sessions';
export { SAMPLE_WORLDS } from './samples/worlds';

export { DEMO_FLAG, SAMPLE_SYSTEM_INFO } from './system';
export { SAMPLE_ASSETS } from './assets';
export { SAMPLE_CONTEXT } from './context';
export { mockWorldBookTest } from './worldbook-test';
export { STATE_LABEL, mockStream, mockStoryStream } from './stream';
export type { MockStreamHandle } from './stream';
