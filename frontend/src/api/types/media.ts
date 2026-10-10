/** 媒体契约：出图任务 / 素材（依据 openapi.yaml）。 */

/* ----------------------------------------------------------------- Images */

export interface ImageJobCreateRequest {
  prompt: string;
  negative_prompt?: string;
  width?: number;
  height?: number;
  seed?: number;
  steps?: number | null;
  workflow_template_id?: string | null;
  card_id?: string | null;
  session_id?: string | null;
  message_id?: string | null;
}

export interface ImageJob {
  id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  provider: string;
  prompt_id: string | null;
  card_id: string | null;
  session_id: string | null;
  message_id: string | null;
  asset_id: string | null;
  archived: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
}

/* ----------------------------------------------------------------- Assets */

export type AssetKind = 'avatar' | 'gallery' | 'background' | 'generated';

export interface Asset {
  id: string;
  kind: AssetKind;
  filename: string;
  content_type: string;
  size_bytes: number;
  card_id: string | null;
  session_id: string | null;
  message_id: string | null;
  tags: string[];
  meta: Record<string, unknown>;
  created_at: string;
}
