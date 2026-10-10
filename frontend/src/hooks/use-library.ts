import { useEffect, useMemo, useState } from 'react';
import type { SearchQuery, SortField, SortOrder } from '@/api/types';

/** 输入防抖：搜索框边打边搜会让 pg_trgm 查询过密，统一 250ms */
export function useDebouncedValue<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export interface LibraryController {
  /** 输入框即时值 */
  query: string;
  setQuery: (v: string) => void;
  /** 防抖后、真正发给 API 的值 */
  debouncedQuery: string;
  tags: string[];
  setTags: (t: string[]) => void;
  toggleTag: (t: string) => void;
  sort: SortField;
  setSort: (s: SortField) => void;
  order: SortOrder;
  setOrder: (o: SortOrder) => void;
  page: number;
  setPage: (p: number) => void;
  /** 传给 TanStack Query 的完整检索参数 */
  searchQuery: SearchQuery;
  /** 是否处于"已筛选"状态（用于空状态区分"真的没有" vs "筛没了"） */
  isFiltering: boolean;
  reset: () => void;
}

/**
 * 内容库检索控制器（P0 F16）：关键词 + 标签 + 排序 + 分页。
 * 与 openapi 的 SearchQuery 语义一致（q / tags / sort / order / page）。
 */
export function useLibraryController(initial?: Partial<SearchQuery>): LibraryController {
  const [query, setQuery] = useState(initial?.q ?? '');
  const [tags, setTags] = useState<string[]>(initial?.tags ?? []);
  const [sort, setSort] = useState<SortField>(initial?.sort ?? 'updated_at');
  const [order, setOrder] = useState<SortOrder>(initial?.order ?? 'desc');
  const [page, setPage] = useState(initial?.page ?? 1);
  const debouncedQuery = useDebouncedValue(query, 250);

  // 关键词/标签变化时回到第 1 页，避免"第 3 页却没有结果"的困惑
  useEffect(() => {
    setPage(1);
  }, [debouncedQuery, tags, sort, order]);

  const searchQuery = useMemo<SearchQuery>(
    () => ({
      q: debouncedQuery || undefined,
      tags: tags.length > 0 ? tags : undefined,
      sort,
      order,
      page,
      limit: 24,
    }),
    [debouncedQuery, tags, sort, order, page],
  );

  return {
    query,
    setQuery,
    debouncedQuery,
    tags,
    setTags,
    toggleTag: (t) => setTags((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t])),
    sort,
    setSort,
    order,
    setOrder,
    page,
    setPage,
    searchQuery,
    isFiltering: Boolean(debouncedQuery) || tags.length > 0,
    reset: () => {
      setQuery('');
      setTags([]);
      setSort('updated_at');
      setOrder('desc');
      setPage(1);
    },
  };
}

/** 从数据集聚合标签（带出现次数，按频次降序） */
export function aggregateTags(items: Array<{ tags?: string[] }>): string[] {
  const counter = new Map<string, number>();
  for (const item of items) {
    for (const tag of item.tags ?? []) {
      counter.set(tag, (counter.get(tag) ?? 0) + 1);
    }
  }
  return [...counter.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([t]) => t);
}
