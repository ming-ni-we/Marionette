/** 内容实体契约：角色卡 / 世界书 / 预设，依据 openapi.yaml 派生。 */

/* ------------------------------------------------------------------ Cards */

export interface CardData {
  name: string;
  description: string;
  personality: string;
  scenario: string;
  first_mes: string;
  mes_example: string;
  creator_notes: string;
  system_prompt: string;
  post_history_instructions: string;
  alternate_greetings: string[];
  tags: string[];
  creator: string;
  character_version: string;
  character_book?: WorldBookData | null;
  extensions?: Record<string, unknown>;
}

export interface CardInput {
  spec: 'rpg_card';
  spec_version: string;
  data: CardData;
  extensions?: Record<string, unknown>;
}

export interface Card extends CardInput {
  id: string;
  created_at: string;
  updated_at: string;
}

/* -------------------------------------------------------------- WorldBooks */

export type WorldBookPosition =
  | 'before_char'
  | 'after_char'
  | 'before_example'
  | 'after_example'
  | 'at_depth';

export interface WorldBookEntry {
  id?: string;
  keys: string[];
  secondary_keys: string[];
  content: string;
  comment: string;
  enabled: boolean;
  constant: boolean;
  selective: boolean;
  case_sensitive: boolean;
  match_whole_words: boolean;
  use_regex: boolean;
  regex_flags: string;
  insertion_order: number;
  priority: number;
  position: WorldBookPosition;
  depth: number;
  role: 'system' | 'user' | 'assistant';
  vector_recall: boolean;
  vector_threshold: number;
  token_count?: number;
  extensions?: Record<string, unknown>;
}

export interface WorldBookData {
  name: string;
  description: string;
  scan_depth: number;
  token_budget: number;
  recursive_scanning: boolean;
  max_recursion_depth: number;
  entries: WorldBookEntry[];
  extensions?: Record<string, unknown>;
}

export interface WorldBookInput {
  spec: 'rpg_worldbook';
  spec_version: string;
  data: WorldBookData;
  extensions?: Record<string, unknown>;
}

export interface WorldBook extends WorldBookInput {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface WorldBookTestRequest {
  sample_text: string;
  scan_depth?: number | null;
}

/** 世界书命中测试的三种可视化状态（本产品差异化视觉点） */
export type WorldBookMatchState = 'miss' | 'hit_in_budget' | 'hit_evicted';

export type WorldBookMatchType = 'constant' | 'keyword' | 'regex' | 'vector' | 'none';

export interface WorldBookTestEntry {
  entry_id: string;
  comment: string;
  matched: boolean;
  match_type: WorldBookMatchType;
  matched_key: string | null;
  in_budget: boolean;
  token_count: number;
  final_position: string | null;
}

export interface WorldBookTestResult {
  entries: WorldBookTestEntry[];
  total_tokens: number;
  token_budget: number;
}

/* ----------------------------------------------------------------- Presets */

export interface PresetSampling {
  temperature: number;
  top_p: number;
  top_k: number;
  min_p: number;
  repetition_penalty: number;
  frequency_penalty: number;
  presence_penalty: number;
  max_tokens: number;
  seed: number;
  stop: string[];
}

export interface PresetData {
  name: string;
  description: string;
  sampling: PresetSampling;
  prompt_template: {
    system: string;
    instruction: string;
    chat_separator: string;
    placeholders: Record<string, string>;
  };
  context_budget: {
    max_context_tokens: number;
    reserve_for_output: number;
    character_pct: number;
    world_info_pct: number;
    memory_pct: number;
    vector_recall_pct: number;
    history_pct: number;
  };
  memory: {
    summarize_every_n_turns: number;
    summary_trigger_ratio: number;
    vector_top_k: number;
    extract_facts: boolean;
  };
  image_hook: {
    enabled: boolean;
    mode: 'manual' | 'every_n_turns' | 'on_scene_change';
    every_n_turns: number;
    workflow_template_id: string | null;
  };
  extensions?: Record<string, unknown>;
}

export interface PresetInput {
  spec: 'rpg_preset';
  spec_version: string;
  data: PresetData;
  extensions?: Record<string, unknown>;
}

export interface Preset extends PresetInput {
  id: string;
  created_at: string;
  updated_at: string;
}
