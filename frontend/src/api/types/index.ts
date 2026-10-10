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
  Message,
  MemoryFact,
  Memory,
  SessionStatus,
  Session,
  SessionCreateRequest,
  SessionUpdateRequest,
  StreamRequest,
  RegenerateRequest,
  ContextSegmentName,
  ContextSegment,
  ContextSnapshot,
  SseWorldInfoEvent,
  SseStartEvent,
  SseDeltaEvent,
  SseUsageEvent,
  SseImageEvent,
  SseDoneEvent,
  SseErrorEvent,
  SseEventMap,
  SseEventName,
} from './session';

export type { ImageJobCreateRequest, ImageJob, AssetKind, Asset } from './media';

/* ----------------------------------------------------- 分页返回的便捷别名 */

import type { Paged } from './common';
import type { Card, Preset, WorldBook } from './content';
import type { Session } from './session';
import type { Asset } from './media';

export type PagedCards = Paged<Card>;
export type PagedWorldBooks = Paged<WorldBook>;
export type PagedPresets = Paged<Preset>;
export type PagedSessions = Paged<Session>;
export type PagedAssets = Paged<Asset>;
