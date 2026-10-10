/** 各资源端点封装（按 SPEC §9 的 REST 约定组织）。 */
import type {
  Asset,
  Card,
  CardInput,
  ConnectionTestResult,
  ContextSnapshot,
  ExportBundleRequest,
  ImageJob,
  ImageJobCreateRequest,
  ImportResult,
  LlmConfig,
  LlmConfigInput,
  Message,
  ModerationConfig,
  PagedAssets,
  PagedCards,
  PagedPresets,
  PagedSessions,
  PagedWorldBooks,
  Preset,
  PresetInput,
  SampleInstallResult,
  SearchQuery,
  SelfCheckResult,
  Session,
  SessionCreateRequest,
  SessionUpdateRequest,
  SystemInfo,
  WorldBook,
  WorldBookInput,
  WorldBookTestRequest,
  WorldBookTestResult,
} from '../types';
import { API_BASE, buildUrl, del, json, jsonPatch, jsonPut, request } from './core';

/* ------------------------------------------------------------------ Auth */

export interface AuthSession {
  authenticated: boolean;
  expires_at?: string;
}

export const authApi = {
  login: (password: string) => request<AuthSession>('/auth/login', json({ password })),
  logout: () => request<unknown>('/auth/logout', { method: 'POST' }),
  session: () => request<AuthSession>('/auth/session'),
};

/* ---------------------------------------------------------------- System */

export const systemApi = {
  info: () => request<SystemInfo>('/system/info'),
  selfcheck: () => request<SelfCheckResult>('/system/selfcheck'),
};

/* ---------------------------------------------------------------- Config */

export const configApi = {
  getLlm: () => request<LlmConfig>('/config/llm'),
  setLlm: (input: LlmConfigInput) => request<LlmConfig>('/config/llm', jsonPut(input)),
  testLlm: (input: LlmConfigInput) => request<ConnectionTestResult>('/config/llm/test', json(input)),
  getModeration: () => request<ModerationConfig>('/config/moderation'),
  setModeration: (input: ModerationConfig) =>
    request<ModerationConfig>('/config/moderation', jsonPut(input)),
  probeComfyUI: (base_url?: string) =>
    request<{ reachable: boolean; device: string | null; checkpoints: string[] }>(
      '/config/comfyui/probe',
      json({ base_url }),
    ),
};

/* ------------------------------------------------------------ Onboarding */

export const onboardingApi = {
  installSamples: () => request<SampleInstallResult>('/onboarding/samples', { method: 'POST' }),
};

/* ----------------------------------------------------------------- Cards */

export const cardsApi = {
  list: (query?: SearchQuery) => request<PagedCards>('/cards', undefined, query),
  get: (cardId: string) => request<Card>(`/cards/${cardId}`),
  create: (input: CardInput) => request<Card>('/cards', json(input)),
  update: (cardId: string, input: CardInput) => request<Card>(`/cards/${cardId}`, jsonPatch(input)),
  remove: (cardId: string) => request<unknown>(`/cards/${cardId}`, del()),
  assets: (cardId: string, query?: SearchQuery) =>
    request<PagedAssets>(`/cards/${cardId}/assets`, undefined, query),
};

/* ------------------------------------------------------------ WorldBooks */

export const worldbooksApi = {
  list: (query?: SearchQuery) => request<PagedWorldBooks>('/worldbooks', undefined, query),
  get: (id: string) => request<WorldBook>(`/worldbooks/${id}`),
  create: (input: WorldBookInput) => request<WorldBook>('/worldbooks', json(input)),
  update: (id: string, input: WorldBookInput) => request<WorldBook>(`/worldbooks/${id}`, jsonPatch(input)),
  remove: (id: string) => request<unknown>(`/worldbooks/${id}`, del()),
  test: (id: string, input: WorldBookTestRequest) =>
    request<WorldBookTestResult>(`/worldbooks/${id}/test`, json(input)),
};

/* --------------------------------------------------------------- Presets */

export const presetsApi = {
  list: (query?: SearchQuery) => request<PagedPresets>('/presets', undefined, query),
  get: (id: string) => request<Preset>(`/presets/${id}`),
  create: (input: PresetInput) => request<Preset>('/presets', json(input)),
  update: (id: string, input: PresetInput) => request<Preset>(`/presets/${id}`, jsonPatch(input)),
  remove: (id: string) => request<unknown>(`/presets/${id}`, del()),
};

/* -------------------------------------------------------------- Sessions */

export const sessionsApi = {
  list: (query?: SearchQuery) => request<PagedSessions>('/sessions', undefined, query),
  get: (id: string, includeMessages = true) =>
    request<Session>(
      `/sessions/${id}`,
      undefined,
      includeMessages ? { include_messages: true } : { include_messages: false },
    ),
  create: (input: SessionCreateRequest) => request<Session>('/sessions', json(input)),
  update: (id: string, input: SessionUpdateRequest) =>
    request<Session>(`/sessions/${id}`, jsonPatch(input)),
  remove: (id: string) => request<unknown>(`/sessions/${id}`, del()),
  appendMessage: (id: string, body: { role: string; content: string }) =>
    request<Message>(`/sessions/${id}/messages`, json(body)),
  interrupt: (id: string) =>
    request<{ interrupted: boolean }>(`/sessions/${id}/interrupt`, { method: 'POST' }),
  fork: (id: string, body: { from_message_id?: string; title?: string }) =>
    request<Session>(`/sessions/${id}/fork`, json(body)),
  lastContext: (id: string) => request<ContextSnapshot>(`/sessions/${id}/last-context`),
};

/* ----------------------------------------------------------------- Images */

export const imagesApi = {
  createJob: (input: ImageJobCreateRequest) => request<ImageJob>('/images/jobs', json(input)),
  getJob: (jobId: string) => request<ImageJob>(`/images/jobs/${jobId}`),
};

/* ----------------------------------------------------------------- Assets */

export const assetsApi = {
  list: (query?: SearchQuery & { card_id?: string; kind?: string }) =>
    request<PagedAssets>('/assets', undefined, query),
  get: (assetId: string) => request<Asset>(`/assets/${assetId}`),
  remove: (assetId: string) => request<unknown>(`/assets/${assetId}`, del()),
  contentUrl: (assetId: string) => `${API_BASE}/assets/${assetId}/content`,
  upload: (form: FormData) => request<Asset>('/assets', { method: 'POST', body: form }),
};

/* ---------------------------------------------------------- Import/Export */

export const ioApi = {
  importCard: (file: File, onConflict: 'rename' | 'overwrite' | 'skip' = 'rename') => {
    const form = new FormData();
    form.append('file', file);
    form.append('on_conflict', onConflict);
    return request<ImportResult>('/import/card', { method: 'POST', body: form });
  },
  importWorldBook: (file: File, onConflict: 'rename' | 'overwrite' | 'skip' = 'rename') => {
    const form = new FormData();
    form.append('file', file);
    form.append('on_conflict', onConflict);
    return request<ImportResult>('/import/worldbook', { method: 'POST', body: form });
  },
  exportBundle: (input: ExportBundleRequest) =>
    fetch(buildUrl('/export/bundle'), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  exportCardUrl: (cardId: string, format: 'json' | 'png' = 'json') =>
    `${API_BASE}/export/card/${cardId}?format=${format}`,
};

/* ------------------------------------------------------------------ 埋点 */

export const eventsApi = {
  record: (name: string, properties?: Record<string, unknown>) =>
    request<unknown>('/events', json({ name, properties })).catch(() => undefined),
};
