/**
 * 素材库演示数据（后端不可达时使用，UI 会标注「演示数据」）。
 */
import type { Asset } from '@/api/types';
import { SAMPLE_CARDS } from './samples/cards';
import { SAMPLE_SESSIONS } from './samples/sessions';
import { T0, T1 } from './samples/shared';

export const SAMPLE_ASSETS: Asset[] = [
  {
    id: 'a1f0a1e2-0001-4e01-9d01-000000000001',
    kind: 'avatar',
    filename: 'su-wan-avatar.png',
    content_type: 'image/png',
    size_bytes: 248_320,
    card_id: SAMPLE_CARDS[0].id,
    session_id: null,
    message_id: null,
    tags: ['头像', '苏晚'],
    meta: { width: 768, height: 768 },
    created_at: T0,
  },
  {
    id: 'a1f0a1e2-0002-4e02-9d02-000000000002',
    kind: 'generated',
    filename: 'scene-bookstore-rain.png',
    content_type: 'image/png',
    size_bytes: 1_842_000,
    card_id: SAMPLE_CARDS[0].id,
    session_id: SAMPLE_SESSIONS[0].id,
    message_id: 'm-0003',
    tags: ['场景', '雨天', '书店'],
    meta: {
      prompt: 'rainy dusk, old bookstore interior, warm tungsten light',
      seed: 41827,
      width: 1024,
      height: 1024,
    },
    created_at: T1,
  },
  {
    id: 'a1f0a1e2-0003-4e03-9d03-000000000003',
    kind: 'background',
    filename: 'bg-oldtown-street.png',
    content_type: 'image/png',
    size_bytes: 2_310_400,
    card_id: null,
    session_id: null,
    message_id: null,
    tags: ['背景', '旧城区'],
    meta: { width: 1536, height: 1024 },
    created_at: T0,
  },
];
