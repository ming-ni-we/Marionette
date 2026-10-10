import type { Preset } from '@/api/types';
import { T0 } from './shared';

export const SAMPLE_PRESETS: Preset[] = [
  {
    id: 'p1f0a1e2-0001-4c01-9b01-000000000001',
    spec: 'rpg_preset',
    spec_version: '1.0',
    data: {
      name: '日常向 · 稳',
      description: '适合慢节奏日常会话：温度略低、重复惩罚略高，减少跑题。',
      sampling: {
        temperature: 0.78,
        top_p: 0.93,
        top_k: 40,
        min_p: 0.05,
        repetition_penalty: 1.12,
        frequency_penalty: 0,
        presence_penalty: 0,
        max_tokens: 1024,
        seed: -1,
        stop: [],
      },
      prompt_template: {
        system:
          '你正在扮演 {{char}}。以第一人称沉浸式回应，动作与对话自然交织。不要替 {{user}} 决定行动或感受。',
        instruction: '保持既定人设与场景连贯，不引入与设定冲突的元素。',
        chat_separator: '\n',
        placeholders: {},
      },
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
    },
    created_at: T0,
    updated_at: T0,
  },
];
