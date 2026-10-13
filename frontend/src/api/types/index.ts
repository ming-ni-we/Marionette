/**
 * API 类型契约总出口 —— 前后端唯一共享契约
 * -----------------------------------------------------------------------------
 * 依据 `docs/spec/openapi.yaml` 手写派生；字段名与 openapi 逐字对齐（snake_case）。
 * 任何变更必须先改 `docs/spec/openapi.yaml`，再改本目录下的分域文件。
 *
 * 导入方式不变：`import type { Card, Session } from '@/api/types';`
 * -----------------------------------------------------------------------------
 */
export type { Envelope, ErrorEnvelope, ErrorClass, SortField, SortOrder, SearchQuery, Paged } from './common';
export type { ImportResult, ExportBundleRequest, SampleInstallResult } from './common';

export type {
  SystemInfo,
  SelfCheckItem,
  SelfCheckResult,
  LlmProvider,
  LlmConfigInput,
  LlmConfig,
  ConnectionTestResult,
  ModerationConfig,
} from './system';

export type {
  CardData,
  CardInput,
  Card,
  WorldBookPosition,
  WorldBookEntry,
  WorldBookData,
  WorldBookInput,
  WorldBook,
  WorldBookTestRequest,
  WorldBookMatchState,
  WorldBookMatchType,
  WorldBookTestEntry,
  WorldBookTestResult,
  PresetSampling,
  PresetData,
  PresetInput,
  Preset,
} from './content';

export type {
  Scene,
  SessionState,
  StateMachine,
  MessageMeta,
  BeatRole,
  Message,
  MemoryFact,
  Memory,
  SessionStatus,
  Session,
  SessionCreateRequest,
  SessionUpdateRequest,
  StreamRequest,
  RegenerateRequest,
  /* ---- 剧情模式（多角色）---- */
  StoryState,
  SceneStory,
  CastMember,
  Relation,
  StorySnapshot,
  ContextSegmentName,
  ContextSegment,
  ContextBudget,
  ContextSnapshot,
  SseWorldInfoEvent,
  SseStartEvent,
  SseDeltaEvent,
  SseUsageEvent,
  SseImageEvent,
  SseDoneEvent,
  SseErrorEvent,
  SseDirectorEvent,
  SseSpeakerSwitchEvent,
  SseNodeEvent,
  SseActionsEvent,
  ActionSuggestion,
  ActionTone,
  ActionsResponse,
  SseEventMap,
  SseEventName,
} from './session';

export { RPG_SPEC, STORY_SPEC, STORY_ONLY_EVENTS } from './session';

export type { ImageJobCreateRequest, ImageJob, AssetKind, Asset } from './media';

export type {
  World,
  WorldInput,
  WorldPatch,
  WorldSetting,
  WorldFaction,
  WorldCastMember,
  WorldRelation,
  WorldOutline,
  WorldOutlineNode,
} from './world';

export { emptyWorld, nextEntityId } from './world';

/* ----------------------------------------------------- 分页返回的便捷别名 */

import type { Paged } from './common';
import type { Card, Preset, WorldBook } from './content';
import type { Session } from './session';
import type { Asset } from './media';
import type { World } from './world';

export type PagedCards = Paged<Card>;
export type PagedWorldBooks = Paged<WorldBook>;
export type PagedPresets = Paged<Preset>;
export type PagedSessions = Paged<Session>;
export type PagedAssets = Paged<Asset>;
export type PagedWorlds = Paged<World>;
