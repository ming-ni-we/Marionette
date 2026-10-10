/** 系统信息与配置契约（System / Config），依据 openapi.yaml 派生。 */
import type { ErrorClass } from './common';

/* ------------------------------------------------------------------ System */

export interface SystemInfo {
  app_version: string;
  schema_versions: { card: string; worldbook: string; preset: string; session: string };
  llm_provider: string;
  llm_model: string;
  embedding_model: string;
  gpu_available: boolean;
  image_provider: string;
}

export interface SelfCheckItem {
  name: string;
  status: 'ok' | 'warn' | 'fail';
  detail: string;
  fix_hint: string;
}

export interface SelfCheckResult {
  overall: 'ok' | 'degraded' | 'failed';
  checks: SelfCheckItem[];
  port_in_use: boolean;
  suggested_port: number;
}

/* ------------------------------------------------------------------ Config */

export type LlmProvider = 'ollama' | 'openai_compatible' | 'zhipu' | 'dashscope' | 'deepseek';

export interface LlmConfigInput {
  provider: LlmProvider;
  base_url: string;
  api_key?: string;
  model: string;
  context_window?: number;
  extra?: Record<string, unknown>;
}

export interface LlmConfig extends LlmConfigInput {
  active: boolean;
  updated_at: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  latency_ms: number;
  error_class: ErrorClass | null;
  message: string;
  model_seen: string | null;
}

export interface ModerationConfig {
  enabled: boolean;
  check_input: boolean;
  check_output: boolean;
  provider: 'builtin_wordlist' | 'cloud';
  rules: {
    blocked_words: string[];
    block_on_match: boolean;
    label_ai_generated: boolean;
  };
  updated_at?: string;
}
