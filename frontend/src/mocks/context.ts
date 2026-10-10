/**
 * 上下文装配快照演示数据（引擎可见面板用，后端不可达时使用）。
 * 分段 token 数用于展示「预算分配」条与「预估 vs 实际」对比。
 */
import type { ContextSnapshot } from '@/api/types';
import { T1 } from './samples/shared';

export const SAMPLE_CONTEXT: ContextSnapshot = {
  prompt_text:
    '[系统基座] 你正在扮演 {{char}}…\n[角色定义] 苏晚 / 旧城区未名书店店主…\n[世界书·before_char] 【地点基调】旧城区…\n[长期记忆] 玩家在梅雨季傍晚躲雨进「未名书店」…\n[历史] …\n[历史后指令] 保持克制、生活化的语感…',
  segments: [
    { name: 'system', token_count: 142 },
    { name: 'character', token_count: 386 },
    { name: 'world_info_before', token_count: 96 },
    { name: 'memory', token_count: 214 },
    { name: 'examples', token_count: 168 },
    { name: 'history', token_count: 512 },
    { name: 'world_info_at_depth', token_count: 0 },
    { name: 'post_history', token_count: 64 },
  ],
  world_info_trace: [],
  budget: { max_context_tokens: 8192, used_tokens: 1582, reserve_for_output: 1024 },
  estimated_prompt_tokens: 1582,
  actual_prompt_tokens: 1601,
  assembled_at: T1,
};
