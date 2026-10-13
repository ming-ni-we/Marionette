/**
 * 世界观契约（剧情引擎）。
 * -----------------------------------------------------------------------------
 * 对齐 `backend/app/schemas/world.py`。与角色卡/世界书的差异：这里没有 `data`
 * 包裹层——`setting`/`factions`/`cast`/`relations`/`outline` 直接摊平在对象上，
 * 因为导演需要按维度独立读写（例如只更新 outline 而不动 cast）。
 *
 * 铁律：字段名与后端逐字对齐（snake_case）；未知字段一律保留（`[k: string]`），
 * 保证后端加字段时前端不会静默丢数据。
 * -----------------------------------------------------------------------------
 */

/** 世界内部结构件。 */
export interface WorldFaction {
  id: string;
  name: string;
  /** 立场：友好 / 中立 / 敌对 / 未知 */
  stance?: string;
  description?: string;
  [k: string]: unknown;
}

/**
 * 剧情角色群成员。
 * `id` 是剧情内的稳定标识（`speaker_id` 与关系图都引用它），
 * `card_id` 可选——填了就关联到已有角色卡，复用其人设与头像。
 */
export interface WorldCastMember {
  id: string;
  name: string;
  /** 主角 / 配角 / 反派 / 路人 */
  role?: string;
  /** 说话风格，供导演写台词时对齐语气 */
  voice?: string;
  goals?: string[];
  description?: string;
  card_id?: string | null;
  [k: string]: unknown;
}

/** 角色关系图的一条边（tension ∈ [-1,1]：负为敌意，正为亲密）。 */
export interface WorldRelation {
  from: string;
  to: string;
  /** 旧识 / 上下级 / 宿敌 / 血亲 */
  kind?: string;
  tension?: number;
  note?: string;
  [k: string]: unknown;
}

/** 剧情大纲的关键节点。 */
export interface WorldOutlineNode {
  id: string;
  title?: string;
  brief?: string;
  /** 触发条件的自然语言描述，由导演判断是否满足 */
  trigger?: string;
  [k: string]: unknown;
}

export interface WorldOutline {
  main_goal?: string;
  nodes?: WorldOutlineNode[];
  /** 结局倾向（开放式描述） */
  endings?: string[];
  [k: string]: unknown;
}

export interface WorldSetting {
  /** 时代背景 */
  era?: string;
  /** 核心地点 */
  locations?: string[];
  /** 世界规则（模型必须遵守的硬约束） */
  rules?: string[];
  /** 氛围基调 */
  tone?: string;
  /** 一句话总览 */
  summary?: string;
  [k: string]: unknown;
}

/** 世界观对象。 */
export interface World {
  id: string;
  spec: string;
  spec_version: string;
  title: string;
  setting: WorldSetting;
  factions: WorldFaction[];
  cast: WorldCastMember[];
  relations: WorldRelation[];
  outline: WorldOutline;
  /** 序幕文本：新建剧情会话时作为开场白底本 */
  opening: string;
  extensions: Record<string, unknown>;
  tags: string[];
  created_at: string | null;
  updated_at: string | null;
}

/** 创建入参（`id`/时间戳由后端生成）。 */
export type WorldInput = Omit<World, 'id' | 'created_at' | 'updated_at'> & {
  spec?: string;
  spec_version?: string;
};

/** PATCH 入参：只传要改的键。 */
export type WorldPatch = Partial<WorldInput>;

/** 空世界观模板（新建页初值）。 */
export function emptyWorld(): WorldInput {
  return {
    spec: 'rpg_world',
    spec_version: '1.0',
    title: '',
    setting: { era: '', locations: [], rules: [], tone: '', summary: '' },
    factions: [],
    cast: [],
    relations: [],
    outline: { main_goal: '', nodes: [], endings: [] },
    opening: '',
    extensions: {},
    tags: [],
  };
}

/** 生成 `c1`/`c2`… 这类稳定的剧情内 id（关系图与 speaker_id 都靠它对齐）。 */
export function nextEntityId(prefix: string, existing: Array<{ id?: string }>): string {
  const used = new Set(existing.map((e) => String(e.id || '')));
  for (let i = 1; i <= existing.length + 1; i += 1) {
    const candidate = `${prefix}${i}`;
    if (!used.has(candidate)) return candidate;
  }
  return `${prefix}${Date.now()}`;
}
