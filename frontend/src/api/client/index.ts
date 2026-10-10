/**
 * API 客户端总出口 —— 导入方式对外保持稳定：
 *   `import { sessionsApi, streamChat, setUnauthorizedHandler } from '@/api/client';`
 * 内部按 内核 / 资源端点 / SSE 三块拆分，单文件各自收敛在 300 行内。
 */
export { ApiError, API_BASE, setUnauthorizedHandler, notifyUnauthorized, buildUrl, request } from './core';
export {
  authApi,
  systemApi,
  configApi,
  onboardingApi,
  cardsApi,
  worldbooksApi,
  presetsApi,
  sessionsApi,
  imagesApi,
  assetsApi,
  ioApi,
  eventsApi,
  type AuthSession,
} from './resources';
export { streamChat, regenerateChat, type StreamCallbacks } from './stream';

/* --------------------------------------------------- 便捷构造（新建草稿） */

import type { CardData, PresetData, WorldBookData } from '../types';

export const emptyCardData = (): CardData => ({
  name: '',
  description: '',
  personality: '',
  scenario: '',
  first_mes: '',
  mes_example: '',
  creator_notes: '',
  system_prompt: '',
  post_history_instructions: '',
  alternate_greetings: [],
  tags: [],
  creator: '',
  character_version: '1.0',
  character_book: null,
  extensions: {},
});

export const emptyWorldBookData = (): WorldBookData => ({
  name: '',
  description: '',
  scan_depth: 4,
  token_budget: 1024,
  recursive_scanning: false,
  max_recursion_depth: 3,
  entries: [],
  extensions: {},
});

export const emptyPresetData = (): PresetData => ({
  name: '',
  description: '',
  sampling: {
    temperature: 0.8,
    top_p: 0.95,
    top_k: 40,
    min_p: 0.05,
    repetition_penalty: 1.1,
    frequency_penalty: 0,
    presence_penalty: 0,
    max_tokens: 1024,
    seed: -1,
    stop: [],
  },
  prompt_template: { system: '', instruction: '', chat_separator: '\n', placeholders: {} },
  context_budget: {
    max_context_tokens: 8192,
    reserve_for_output: 1024,
    character_pct: 15,
    world_info_pct: 25,
    memory_pct: 15,
    vector_recall_pct: 5,
    history_pct: 35,
  },
  memory: {
    summarize_every_n_turns: 10,
    summary_trigger_ratio: 0.8,
    vector_top_k: 5,
    extract_facts: true,
  },
  image_hook: { enabled: false, mode: 'manual', every_n_turns: 10, workflow_template_id: null },
  extensions: {},
});

/* ---------------------------------------------------------------- 类型转发 */

export type { Paged, Card, WorldBook, Preset, Session, Asset } from '../types';
