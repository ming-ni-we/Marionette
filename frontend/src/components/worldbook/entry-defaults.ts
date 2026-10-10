import type { WorldBookEntry } from '@/api/types';

/** 新条目的默认值（与后端 WorldBookEntry 缺省语义一致）。 */
export function newEntry(): WorldBookEntry {
  return {
    keys: [],
    secondary_keys: [],
    content: '',
    comment: '',
    enabled: true,
    constant: false,
    selective: false,
    case_sensitive: false,
    match_whole_words: false,
    use_regex: false,
    regex_flags: 'i',
    insertion_order: 100,
    priority: 50,
    position: 'after_char',
    depth: 4,
    role: 'system',
    vector_recall: false,
    vector_threshold: 0.75,
  };
}
