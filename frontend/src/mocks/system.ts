/**
 * 系统信息演示数据（后端不可达时使用，UI 会标注「演示数据」）。
 */
import type { SystemInfo } from '@/api/types';

/** 离线演示数据的统一标注文案（UI 必须显示，禁止伪装成真实数据）。 */
export const DEMO_FLAG = '演示数据 · 后端未连接';

export const SAMPLE_SYSTEM_INFO: SystemInfo = {
  app_version: '1.0.0',
  schema_versions: { card: '1.0', worldbook: '1.0', preset: '1.0', session: '1.0' },
  llm_provider: 'openai_compatible',
  llm_model: 'qwen3-14b-instruct',
  embedding_model: 'bge-large-zh-v1.5',
  gpu_available: false,
  image_provider: 'cloud',
};
