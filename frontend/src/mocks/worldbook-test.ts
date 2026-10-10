/**
 * 世界书命中测试（本地简化实现，与后端 WorldBookEngine 语义对齐）。
 * 三态输出是「提线」的差异化视觉点：
 *   - matched=false                        → 未命中
 *   - matched=true  && in_budget=true      → 命中且在预算内
 *   - matched=true  && in_budget=false     → 命中但被 token 预算挤出
 */
import type { WorldBookData, WorldBookTestEntry, WorldBookTestResult } from '@/api/types';

export function mockWorldBookTest(
  data: WorldBookData,
  sampleText: string,
  scanDepth = 4,
): WorldBookTestResult {
  void scanDepth;
  const text = sampleText.toLowerCase();
  const hits: WorldBookTestEntry[] = data.entries.map((entry) => {
    const base = {
      entry_id: entry.id ?? entry.comment,
      comment: entry.comment || entry.keys.join(' / ') || '（未命名条目）',
      token_count: entry.token_count ?? Math.ceil(entry.content.length / 1.6),
    };

    if (!entry.enabled) {
      return {
        ...base,
        matched: false,
        match_type: 'none',
        matched_key: null,
        in_budget: false,
        final_position: null,
      };
    }
    if (entry.constant) {
      return {
        ...base,
        matched: true,
        match_type: 'constant',
        matched_key: null,
        in_budget: true,
        final_position: entry.position,
      };
    }
    const hitKey = entry.keys.find((k) => text.includes(k.toLowerCase())) ?? null;
    const secondaryOk =
      !entry.selective || entry.secondary_keys.some((k) => text.includes(k.toLowerCase()));
    if (!hitKey || !secondaryOk) {
      return {
        ...base,
        matched: false,
        match_type: 'none',
        matched_key: null,
        in_budget: false,
        final_position: null,
      };
    }
    return {
      ...base,
      matched: true,
      match_type: entry.use_regex ? 'regex' : 'keyword',
      matched_key: hitKey,
      in_budget: true,
      final_position: entry.position,
    };
  });

  // 预算裁决：命中项按 priority 降序保留，超预算者标记为被挤出
  const budget = data.token_budget;
  let used = 0;
  const ordered = data.entries
    .map((e, i) => ({ e, i }))
    .filter(({ i }) => hits[i].matched)
    .sort((a, b) => b.e.priority - a.e.priority);

  for (const { i } of ordered) {
    const cost = hits[i].token_count;
    if (used + cost <= budget) {
      used += cost;
    } else {
      hits[i] = { ...hits[i], in_budget: false, final_position: null };
    }
  }

  return { entries: hits, total_tokens: used, token_budget: budget };
}
