/**
 * API 客户端内核 —— 统一响应信封解包 + 401 全局处理
 * -----------------------------------------------------------------------------
 * - 后端统一信封 { code, data, message }，成功 code=0；本层解包后直接返回 data
 * - 401 → 触发全局未授权处理（路由跳 /login），不泄露内容
 * - 所有请求 credentials: 'include'（HttpOnly 会话令牌）
 * -----------------------------------------------------------------------------
 */
import type { Envelope, ErrorClass, SearchQuery } from '../types';

export const API_BASE = '/api/v1';

/** 结构化的 API 错误，保留后端 code 与 error_class 供 UI 分类展示 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: number;
  readonly errorClass: ErrorClass | null;

  constructor(status: number, code: number, message: string, errorClass: ErrorClass | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.errorClass = errorClass;
  }
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/** 由路由层注册：401 时跳转登录页（避免用 window.location 造成整页刷新丢失状态） */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

/** 通知全局未授权（供 SSE 等非 request 路径复用） */
export function notifyUnauthorized(): void {
  onUnauthorized?.();
}

export function buildUrl(path: string, query?: SearchQuery & Record<string, unknown>): string {
  const url = `${API_BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      // tags 多值：form + explode=true
      for (const v of value) params.append(key, String(v));
    } else {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

export async function parseError(res: Response): Promise<ApiError> {
  let code = res.status;
  let message = `请求失败（HTTP ${res.status}）`;
  let errorClass: ErrorClass | null = null;
  try {
    const body = (await res.json()) as {
      code?: number;
      message?: string;
      error_class?: ErrorClass;
    };
    if (typeof body.code === 'number') code = body.code;
    if (body.message) message = body.message;
    if (body.error_class) errorClass = body.error_class;
  } catch {
    // 非 JSON 错误体，保留 HTTP 状态
  }
  return new ApiError(res.status, code, message, errorClass);
}

export async function request<T>(
  path: string,
  init?: RequestInit,
  query?: Record<string, unknown>,
): Promise<T> {
  const res = await fetch(buildUrl(path, query), {
    ...init,
    credentials: 'include',
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...init?.headers,
    },
  });

  if (res.status === 401) {
    notifyUnauthorized();
    throw new ApiError(401, 4010, '访问会话已失效，请重新登录', 'auth_failed');
  }
  if (!res.ok) {
    throw await parseError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const body = (await res.json()) as Envelope<T>;
  if (body && typeof body === 'object' && 'code' in body && body.code !== 0) {
    throw new ApiError(res.status, body.code, body.message || '请求被拒绝');
  }
  return body.data;
}

export const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });
export const jsonPatch = (body: unknown): RequestInit => ({ method: 'PATCH', body: JSON.stringify(body) });
export const jsonPut = (body: unknown): RequestInit => ({ method: 'PUT', body: JSON.stringify(body) });
export const del = (): RequestInit => ({ method: 'DELETE' });
