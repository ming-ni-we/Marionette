/** 会话运行时契约：会话 / 消息 / 记忆 / 上下文检视 / SSE 事件（依据 openapi.yaml）。 */
import type { WorldBookMatchType, WorldBookTestEntry } from './content';

export interface Scene {
  location: string;
  time: string;
  mood: string;
  summary: string;
  bg_asset_id: string | null;
}

export type SessionState =
  | 'idle'
  | 'assembling'
  | 'generating'
  | 'post_processing'
  | 'interrupted'
  | 'error';

export interface StateMachine {
  current: SessionState;
  turn: number;
  version: number;
  last_error: { code: number; message: string; at: string } | null;
}

export interface MessageMeta {
  swipe_index?: number;
  swipe_group_id?: string;
  greeting_index?: number | null;
  triggered_entry_ids?: string[];
  image_asset_id?: string | null;
  parent_id?: string | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  status: 'streaming' | 'complete' | 'incomplete';
  token_count: number;
  created_at: string;
  meta?: MessageMeta;
}

export interface MemoryFact {
  key: string;
  value: string;
  confidence: number;
  source_message_id: string | null;
  updated_at: string;
}

export interface Memory {
  rolling_summary: string;
  summary_upto_message_id: string | null;
  facts: MemoryFact[];
}

export type SessionStatus = 'active' | 'paused' | 'archived';

export interface Session {
  id: string;
  spec: string;
  spec_version: string;
  character_card_id: string;
  preset_id: string;
  worldbook_ids: string[];
  user_persona: { name?: string; description?: string };
  status: SessionStatus;
  state_machine: StateMachine;
  scene: Scene;
  messages: Message[];
  triggered_entries: Record<string, unknown>;
  memory: Memory;
  created_at: string;
  updated_at: string;
}

export interface SessionCreateRequest {
  character_card_id: string;
  preset_id: string;
  worldbook_ids?: string[];
  user_persona?: { name?: string; description?: string };
  greeting_index?: number;
}

export interface SessionUpdateRequest {
  preset_id?: string;
  worldbook_ids?: string[];
  user_persona?: { name?: string; description?: string };
  status?: SessionStatus;
  scene?: Scene;
}

export interface StreamRequest {
  input: string;
  idempotency_key?: string;
  overrides?: Record<string, unknown>;
}

export interface RegenerateRequest {
  message_id?: string;
  overrides?: Record<string, unknown>;
}

/* --------------------------------------------------------- Context 检视 */

export type ContextSegmentName =
  | 'system'
  | 'character'
  | 'world_info_before'
  | 'memory'
  | 'vector_recall'
  | 'examples'
  | 'history'
  | 'world_info_at_depth'
  | 'post_history';

export interface ContextSegment {
  name: ContextSegmentName;
  token_count: number;
}

export interface ContextSnapshot {
  prompt_text: string;
  segments: ContextSegment[];
  world_info_trace: WorldBookTestEntry[];
  budget: { max_context_tokens: number; used_tokens: number; reserve_for_output: number };
  estimated_prompt_tokens: number;
  actual_prompt_tokens: number | null;
  assembled_at: string;
}

/* -------------------------------------------------------------- SSE 事件 */

export interface SseWorldInfoEvent {
  triggered: Array<{ entry_id: string; match_type: WorldBookMatchType; in_budget: boolean }>;
  trace_id: string;
}

export interface SseStartEvent {
  message_id: string;
  estimated_prompt_tokens: number;
}

export interface SseDeltaEvent {
  text: string;
}

export interface SseUsageEvent {
  prompt_tokens: number;
  completion_tokens: number;
}

export interface SseImageEvent {
  asset_id: string;
  job_id: string;
}

export interface SseDoneEvent {
  message_id: string;
  status: string;
}

export interface SseErrorEvent {
  code: number;
  message: string;
}

/** 7 类 SSE 事件 → UI 状态（docs/03-uiux.md §7.5） */
export type SseEventMap = {
  world_info: SseWorldInfoEvent;
  start: SseStartEvent;
  delta: SseDeltaEvent;
  usage: SseUsageEvent;
  image: SseImageEvent;
  done: SseDoneEvent;
  error: SseErrorEvent;
};

export type SseEventName = keyof SseEventMap;
