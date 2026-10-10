import type { LlmProvider, ModerationConfig } from '@/api/types';

/** 支持的模型服务商与其默认端点（选完自动回填 base_url） */
export const PROVIDERS: Array<{ value: LlmProvider; label: string; defaultUrl: string }> = [
  { value: 'openai_compatible', label: 'OpenAI 兼容（通用）', defaultUrl: 'https://api.openai.com/v1' },
  { value: 'deepseek', label: 'DeepSeek', defaultUrl: 'https://api.deepseek.com/v1' },
  {
    value: 'dashscope',
    label: '通义千问（DashScope）',
    defaultUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  },
  { value: 'zhipu', label: '智谱 GLM', defaultUrl: 'https://open.bigmodel.cn/api/paas/v4' },
  { value: 'ollama', label: '本机 Ollama', defaultUrl: 'http://host.docker.internal:11434/v1' },
];

export const PROVIDER_LABEL: Record<LlmProvider, string> = {
  openai_compatible: 'OpenAI 兼容',
  deepseek: 'DeepSeek',
  dashscope: '通义千问',
  zhipu: '智谱 GLM',
  ollama: '本机 Ollama',
};

/** 审核层默认值（后端未就绪时的可编辑草稿，字段与 ModerationConfig 对齐） */
export const DEFAULT_MODERATION: ModerationConfig = {
  enabled: true,
  check_input: true,
  check_output: true,
  provider: 'builtin_wordlist',
  rules: {
    blocked_words: [],
    block_on_match: true,
    label_ai_generated: false,
  },
};
