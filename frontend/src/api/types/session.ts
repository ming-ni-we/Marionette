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

export type BeatRole = 'reply' | 'narration' | 'opening';

export interface MessageMeta {
  swipe_index?: number;
  swipe_group_id?: string;
  greeting_index?: number | null;
  triggered_entry_ids?: string[];
  image_asset_id?: string | null;
  parent_id?: string | null;
  /* ---- 剧情模式（story_session）扩展：1v1 下全部缺省 ---- */
  /** 说话角色 id（旁白为 null） */
  speaker_id?: string | null;
  speaker_name?: string | null;
  speaker_avatar_asset_id?: string | null;
  /** 旁白段（导演写的景/环境描写），渲染为居中斜体而非角色气泡 */
  is_narration?: boolean;
  /** 导演备注（不出话，只提示），与旁白区分 */
  is_director_note?: boolean;
  /** 本条消息所属的剧情节点 id */
  story_node_id?: string | null;
  /** 第几轮（导演裁决计次） */
  turn?: number;
  /** 这一条在拍点里的角色 */
  beat_role?: BeatRole;
  /** 导演给该角色的表演指示（不进气泡，仅供调试面板） */
  direction?: string;
  /** 导演给该角色的意图（同上） */
  intent?: string;
  /**
   * **仅前端本地使用**，不会发给后端、也不会从后端读回。
   *
   * 每轮开演前由 `use-chat-stream` 打上当前轮次标识，用于把
   * 「本轮气泡」和「历史轮次气泡」区分开。
   *
   * 为什么需要它：`delta` 只带 `speaker_id`，前端靠它反查该写进哪条气泡。
   * 但同一个角色在**上一轮**已有气泡，若反查时不限定范围，就会命中旧气泡，
   * 导致本轮回复被追加到用户消息**上方**的历史气泡里。
   */
  _turnKey?: string;
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

/** `spec` 取值：既有 1v1 会话 vs 剧情会话（驱动前端分派不同运行时页）。 */
export const RPG_SPEC = 'rpg_session';
export const STORY_SPEC = 'story_session';

/* ------------------------------------------------------- 剧情模式（多角色） */

/** 剧情状态：导演裁决累积的幕/拍点/旗标/待触发节点。 */
export interface StoryState {
  /** 当前幕（大纲段落）标识 */
  act_id?: string | null;
  /** 当前情节节点 */
  node_id?: string | null;
  /** 已触发过的节点 id 列表 */
  fired_node_ids?: string[];
  /** 已埋下、等待触发的节点 */
  pending_node?: { id: string; title?: string; brief?: string; [k: string]: unknown } | null;
  /** 剧本旗标（任意键值，供条件判定） */
  flags?: Record<string, unknown>;
  /** 导演连续失败次数（≥3 触发熔断降级） */
  director_failures?: number;
  /** 距上次结算推进的轮次 */
  turn?: number;
  [k: string]: unknown;
}

/** 剧情场景态：在 1v1 `Scene` 之上叠加「在场角色 / 上一说话者 / 拍点」。 */
export interface SceneStory {
  present?: string[];
  last_speaker_id?: string | null;
  beat?: number;
  location?: string;
  time?: string;
  mood?: string;
  summary?: string;
  [k: string]: unknown;
}

export interface CastMember {
  id: string;
  name?: string;
  role?: string;
  voice?: string;
  avatar_asset_id?: string | null;
  /** 是否在场（与 `scene.present` 对应） */
  present?: boolean;
  [k: string]: unknown;
}

/** 角色之间的关系边（tension ∈ [-1,1]，负为敌意、正为亲密）。 */
export interface Relation {
  from: string;
  to: string;
  /** 关系类型，如「旧识」「宿敌」 */
  kind?: string;
  /** 张力值 */
  tension?: number;
  /** 供模型理解的一句话描述 */
  note?: string;
  [k: string]: unknown;
}

/** GET /sessions/{id}/story 的响应。 */
export interface StorySnapshot {
  spec: string;
  is_story: boolean;
  world_id: string | null;
  story: StoryState;
  scene: SceneStory;
  cast: CastMember[];
  relations: Relation[];
  /** 上一轮落库的行动建议（S15-1）。老会话可能缺省 → 视作空数组。 */
  suggestions?: ActionSuggestion[];
}

export interface Session {
  id: string;
  spec: string;
  spec_version: string;
  character_card_id: string;
  preset_id: string;
  /** 仅剧情会话有值；1v1 为 null */
  world_id: string | null;
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
  /** 传入即创建剧情会话（后端据此分派 create_story_session） */
  world_id?: string;
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
  | 'post_history'
  /* ---- 剧情模式新增三段（1v1 下不出现）---- */
  | 'story_state'
  | 'relations'
  | 'cast_roster';

export interface ContextSegment {
  name: ContextSegmentName;
  token_count: number;
}

export interface ContextBudget {
  max_context_tokens: number;
  used_tokens: number;
  reserve_for_output: number;
  story_tokens?: number;
  relations_tokens?: number;
  cast_tokens?: number;
}

export interface ContextSnapshot {
  prompt_text: string;
  segments: ContextSegment[];
  world_info_trace: WorldBookTestEntry[];
  budget: ContextBudget;
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

/* ------------------------------------------- 剧情模式新增 4 类 SSE 事件 */

/** 导演裁决：本轮由谁说话、写了什么旁白、改了哪些状态。 */
export interface SseDirectorEvent {
  /** 本轮出场角色（已按导演给出的顺序） */
  speakers: Array<{ id: string; name?: string; direction?: string; intent?: string }>;
  narration: string;
  scene_patch: Record<string, unknown>;
  node_triggered: { id: string; title?: string; brief?: string } | null;
  relation_updates: Relation[];
  flags: Record<string, unknown>;
  /** 导演为什么这样安排（调试/透明性） */
  reason: string;
  /** 是否走了降级链路（模型没给合法 JSON） */
  degraded: boolean;
}

/** 说话人切换：新起一条角色气泡（或旁白条）。 */
export interface SseSpeakerSwitchEvent {
  /** 旁白时为 null */
  speaker_id: string | null;
  speaker_name: string;
  /** true → 本条是旁白（居中斜体），不是角色气泡 */
  is_narration: boolean;
  /** 该说话者对应消息行 id（旁白也带）。缺省表示前端需本地建条 */
  message_id?: string;
}

/** 剧情节点触发。 */
export interface SseNodeEvent {
  id: string;
  title?: string;
  brief?: string;
}

/** 行动建议：本轮结束后给玩家的多选项。 */
export interface SseActionsEvent {
  actions: ActionSuggestion[];
}

/** 一条行动建议。`tone` 决定图标与配色，`label` 是按钮文案。 */
export interface ActionSuggestion {
  id: string;
  label: string;
  hint?: string;
  tone?: ActionTone;
  [k: string]: unknown;
}

export type ActionTone = 'observe' | 'speak' | 'act' | 'move';

/** GET /sessions/{id}/actions 的响应。 */
export interface ActionsResponse {
  actions: ActionSuggestion[];
}

/**
 * SSE 事件 → UI 状态。
 * **1v1 为子集，剧情模式为超集**：旧前端白名单不含后 4 个事件，
 * 收到即静默丢弃，因此新增事件对既有会话零影响。
 */
export type SseEventMap = {
  world_info: SseWorldInfoEvent;
  start: SseStartEvent;
  delta: SseDeltaEvent;
  usage: SseUsageEvent;
  image: SseImageEvent;
  done: SseDoneEvent;
  error: SseErrorEvent;
  /* ---- 剧情模式 ---- */
  director: SseDirectorEvent;
  speaker_switch: SseSpeakerSwitchEvent;
  node: SseNodeEvent;
  actions: SseActionsEvent;
};

export type SseEventName = keyof SseEventMap;

/** 剧情模式独有的事件名（供白名单/快照断言复用）。 */
export const STORY_ONLY_EVENTS = [
  'director',
  'speaker_switch',
  'node',
  'actions',
] as const satisfies readonly SseEventName[];
