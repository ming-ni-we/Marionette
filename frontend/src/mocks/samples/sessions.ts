import type { Session } from '@/api/types';
import { SAMPLE_CARDS } from './cards';
import { SAMPLE_PRESETS } from './presets';
import { SAMPLE_WORLDBOOKS } from './worldbooks';
import { T0, T1 } from './shared';

export const SAMPLE_SESSIONS: Session[] = [
  {
    id: 's1f0a1e2-0001-4d01-9c01-000000000001',
    spec: 'rpg_session',
    spec_version: '1.0',
    character_card_id: SAMPLE_CARDS[0].id,
    preset_id: SAMPLE_PRESETS[0].id,
    worldbook_ids: [SAMPLE_WORLDBOOKS[0].id],
    user_persona: { name: '你', description: '常来书店的熟客。' },
    status: 'active',
    state_machine: { current: 'idle', turn: 12, version: 7, last_error: null },
    scene: {
      location: '未名书店',
      time: '梅雨季 · 傍晚',
      mood: '安静、潮湿',
      summary: '躲雨进店，聊到了外公的怀表。',
      bg_asset_id: null,
    },
    messages: [
      {
        id: 'm-0001',
        role: 'assistant',
        content:
          '风铃响了一声。她从柜台后抬起头，手里的书签停在半页。\n\n「外面的雨比预报的大。」她把红茶杯往你那边推了推，「先坐吧，打烊还早。」',
        status: 'complete',
        token_count: 78,
        created_at: '2026-10-09T08:31:00+08:00',
        meta: { swipe_index: 0 },
      },
      {
        id: 'm-0002',
        role: 'user',
        content: '那就再坐一会儿。你这怀表……好像停了？',
        status: 'complete',
        token_count: 22,
        created_at: '2026-10-09T08:32:10+08:00',
        meta: {},
      },
      {
        id: 'm-0003',
        role: 'assistant',
        content:
          '她把怀表从围裙口袋里拿出来，铜壳上的划痕在灯下像细密的网。\n\n「停在三点十七分。」她拧了两圈发条，齿轮轻轻响了一下，「我外公留下的。他说走不快也不慢，正好陪雨。」\n\n表针没动。她也不看了，把它放回口袋。',
        status: 'complete',
        token_count: 112,
        created_at: '2026-10-09T08:33:00+08:00',
        meta: { swipe_index: 0, triggered_entry_ids: ['e-0002'] },
      },
    ],
    triggered_entries: { 'e-0001': 12, 'e-0002': 1 },
    memory: {
      rolling_summary:
        '玩家在梅雨季傍晚躲雨进「未名书店」，与店主苏晚聊到了她外公留下的黄铜怀表（停在三点十七分）。',
      summary_upto_message_id: 'm-0002',
      facts: [
        {
          key: '地点',
          value: '未名书店（旧城区）',
          confidence: 0.92,
          source_message_id: 'm-0001',
          updated_at: T1,
        },
        {
          key: '关键物件',
          value: '黄铜怀表 · 停在三点十七分 · 外公遗物',
          confidence: 0.88,
          source_message_id: 'm-0003',
          updated_at: T1,
        },
      ],
    },
    created_at: T0,
    updated_at: T1,
  },
  {
    id: 's1f0a1e2-0002-4d02-9c02-000000000002',
    spec: 'rpg_session',
    spec_version: '1.0',
    character_card_id: SAMPLE_CARDS[1].id,
    preset_id: SAMPLE_PRESETS[0].id,
    worldbook_ids: [],
    user_persona: { name: '你', description: '' },
    status: 'paused',
    state_machine: { current: 'idle', turn: 4, version: 2, last_error: null },
    scene: {
      location: '建筑事务所',
      time: '凌晨',
      mood: '疲惫',
      summary: '带着夜宵上门。',
      bg_asset_id: null,
    },
    messages: [],
    triggered_entries: {},
    memory: { rolling_summary: '', summary_upto_message_id: null, facts: [] },
    created_at: T0,
    updated_at: T0,
  },
];
