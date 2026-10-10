/**
 * 通用契约：信封 / 错误分类 / 分页检索 / 导入导出
 * 依据 `docs/spec/openapi.yaml` 手写派生，字段名逐字对齐（snake_case）。
 */

export interface Envelope<T> {
  code: number;
  data: T;
  message?: string;
}

export interface ErrorEnvelope {
  code: number;
  data?: null;
  message: string;
}

/** 连接测试的 7 类错误分类（F1 最大流失点，必须锁定） */
export type ErrorClass =
  | 'model_not_found'
  | 'endpoint_invalid'
  | 'auth_failed'
  | 'quota_exhausted'
  | 'network_unreachable'
  | 'timeout'
  | 'unknown';

/* -------------------------------------------------------------- 分页检索 */

export type SortField = 'created_at' | 'updated_at' | 'name' | 'last_message_at';
export type SortOrder = 'asc' | 'desc';

export interface SearchQuery {
  q?: string;
  tags?: string[];
  sort?: SortField;
  order?: SortOrder;
  page?: number;
  limit?: number;
  /** 资源特有的附加过滤（如 assets 的 card_id / kind、sessions 的 status），透传给查询串 */
  [key: string]: unknown;
}

export interface Paged<T> {
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
  items: T[];
}

/* ---------------------------------------------------------- Import/Export */

export interface ImportResult {
  source_format: 'st_v1' | 'st_v2' | 'st_v3' | 'native';
  object_id: string;
  warnings: string[];
  preserved_unknown_keys: string[];
}

export interface ExportBundleRequest {
  card_ids?: string[];
  worldbook_ids?: string[];
  preset_ids?: string[];
  include_assets?: boolean;
}

export interface SampleInstallResult {
  card_ids: string[];
  worldbook_ids: string[];
  preset_ids: string[];
}
