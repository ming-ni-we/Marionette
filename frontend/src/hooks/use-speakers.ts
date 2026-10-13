import { useMemo } from 'react';
import type { CastMember, Message, Relation } from '@/api/types';

/**
 * 角色视觉身份（avatar identity）。
 * -----------------------------------------------------------------------------
 * 剧情模式一轮里会有多个角色说话，如果所有角色头长得一样，读者分不清谁是谁。
 * 这里做两件事：
 *   1) **稳定映射**——同一个 `speaker_id` 在任何一轮、任何页面刷新后都拿到同一个
 *      色板槽位与同一个首字，不会因为出场顺序变化而变色（否则读者会以为换了人）。
 *   2) **无硬编码色值**——槽位只是 index，具体颜色由 `SPEAKER_TONES` 里的
 *      Tailwind 语义类决定（内部引用 `--color-*` token），符合「禁止硬编码颜色」铁律。
 *
 * 为什么不用 hash：hash 会碰撞，两个主要角色撞到同一槽位就白做了。
 * 我们按「稳定顺序」分配——先按 `cast` 的原始顺序（世界观里的定义顺序，
 * 作者心智里的顺序），再把流式过程中才出现的角色追加到末尾。
 */

/** 槽位数：4 个足够区分一轮里可能同时出场的角色，再多就该靠名字读了。 */
const SLOT_COUNT = 4;

/**
 * 槽位 → 语义类。
 * 只使用既有 token（accent / info / success / warn），不引入新颜色，
 * 深浅两个主题下都自动适配。
 */
const SPEAKER_TONES = [
  'border-accent/40 bg-accent-subtle text-accent',
  'border-info/40 bg-surface-warm text-info',
  'border-success/40 bg-success-subtle text-success',
  'border-warn/40 bg-warn-subtle text-warn',
] as const;

const NARRATION_TONE = 'border-border-soft bg-surface text-meta';
const UNKNOWN_TONE = 'border-border bg-surface text-muted';

/** 单个角色的展示身份。 */
export interface SpeakerIdentity {
  id: string;
  /** 显示名（`speaker_name` > cast.name > 「旁白」/「角色」） */
  name: string;
  /** 头像位文字（取名字首个字符；复姓/外文名也能看） */
  initial: string;
  /** 头像容器类（语义色，无硬编码色值） */
  toneClass: string;
  /** 该角色是否在场（`scene.present` ∩ `cast`） */
  present: boolean;
}

export interface SpeakerIndex {
  /** 按 id 查身份 */
  get: (speakerId?: string | null, fallbackName?: string | null) => SpeakerIdentity;
  /** 旁白专用身份（居中渲染时不用头像，但保留以便统一） */
  narration: SpeakerIdentity;
  /** 按 `cast` 定义顺序排列的在场角色（给角色条用） */
  present: SpeakerIdentity[];
  /** 本轮出场的角色 id 列表（`director.speakers`） */
  order: string[];
}

interface UseSpeakersArgs {
  /** 世界观里的角色名单（快照或 `director.speakers` 合并后的结果） */
  cast: CastMember[];
  /** `scene.present`，缺省视为全员在场 */
  present?: string[];
  /** 角色关系（供 `relationBetween` 复用） */
  relations?: Relation[];
  /** 消息列表——用于把流式过程中才出现的角色兜底纳入索引 */
  messages?: Message[];
}

/**
 * 建立「角色 id → 视觉身份」的稳定索引。
 *
 * 稳定性来自**分配顺序而非出场顺序**：
 *   `cast`（作者定义的顺序）→ `messages` 里出现过但不在 cast 的 id（按首次出现）
 * 这样即使导演第二轮把说话顺序倒过来，同一个人还是同一个颜色。
 */
export function useSpeakers({ cast, present, relations, messages }: UseSpeakersArgs): SpeakerIndex {
  return useMemo(() => {
    const presentSet = new Set(present ?? []);

    /* --- 1. 收集 id 的稳定顺序 -------------------------------- */
    const order: string[] = [];
    const seen = new Set<string>();
    const nameById = new Map<string, string>();
    const presentById = new Map<string, boolean>();

    for (const member of cast) {
      const id = String(member.id ?? '');
      if (!id || seen.has(id)) continue;
      seen.add(id);
      order.push(id);
      if (member.name) nameById.set(id, member.name);
      // `present` 缺省（undefined）时视为在场，避免调用方必须传
      presentById.set(id, presentSet.size === 0 ? true : presentSet.has(id));
    }

    for (const msg of messages ?? []) {
      const id = msg.meta?.speaker_id;
      if (!id || seen.has(id)) continue;
      seen.add(id);
      order.push(id);
      if (msg.meta?.speaker_name) nameById.set(id, msg.meta.speaker_name);
      presentById.set(id, true);
    }

    /* --- 2. 分配槽位 ------------------------------------------ */
    const index = new Map<string, SpeakerIdentity>();
    order.forEach((id, i) => {
      const name = nameById.get(id) || '角色';
      index.set(id, {
        id,
        name,
        initial: name.slice(0, 1),
        toneClass: SPEAKER_TONES[i % SLOT_COUNT],
        present: presentById.get(id) ?? true,
      });
    });

    const narration: SpeakerIdentity = {
      id: '',
      name: '旁白',
      initial: '旁',
      toneClass: NARRATION_TONE,
      present: true,
    };

    const get = (speakerId?: string | null, fallbackName?: string | null): SpeakerIdentity => {
      if (!speakerId) {
        return fallbackName ? { ...narration, name: fallbackName } : narration;
      }
      const hit = index.get(speakerId);
      if (hit) return hit;
      // 运行时才冒出来的角色（后端加了人但前端还没拉到快照）：给一个中性身份，
      // 不占用别人的槽位，也不会因为 index 变化让已渲染的气泡换色。
      const name = fallbackName || '角色';
      return {
        id: speakerId,
        name,
        initial: name.slice(0, 1),
        toneClass: UNKNOWN_TONE,
        present: true,
      };
    };

    return {
      get,
      narration,
      present: order
        .map((id) => index.get(id)!)
        .filter((s) => s.present),
      order,
    };
  }, [cast, present, relations, messages]);
}

/** 取两个角色之间的关系（无向：a→b 与 b→a 都算命中）。 */
export function relationBetween(
  relations: Relation[] | undefined,
  a?: string | null,
  b?: string | null,
): Relation | null {
  if (!relations || !a || !b || a === b) return null;
  return (
    relations.find((r) => (r.from === a && r.to === b) || (r.from === b && r.to === a)) ?? null
  );
}

/**
 * 张力值 → 中文标签 + 徽标语气。
 * `tension ∈ [-1, 1]`：负为敌意、正为亲密（见 `Relation` 定义）。
 */
export function tensionLabel(tension?: number): {
  label: string;
  variant: 'danger' | 'warn' | 'neutral' | 'success';
} {
  if (tension === undefined || tension === null || Number.isNaN(tension)) {
    return { label: '未定', variant: 'neutral' };
  }
  if (tension <= -0.6) return { label: '敌意', variant: 'danger' };
  if (tension < -0.15) return { label: '对立', variant: 'warn' };
  if (tension < 0.15) return { label: '中立', variant: 'neutral' };
  if (tension < 0.6) return { label: '亲近', variant: 'success' };
  return { label: '亲密', variant: 'success' };
}
