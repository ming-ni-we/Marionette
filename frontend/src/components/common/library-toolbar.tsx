import { cn } from '@/lib/utils';
import { Search, Filter, ArrowUpDown, ArrowUp, ArrowDown, X, Tags } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { SortField, SortOrder } from '@/api/types';

const SORT_LABELS: Record<SortField, string> = {
  updated_at: '最近修改',
  created_at: '创建时间',
  name: '名称',
  last_message_at: '最近对话',
};

interface LibraryToolbarProps {
  query: string;
  onQueryChange: (value: string) => void;
  placeholder?: string;
  /** 已选标签 */
  selectedTags: string[];
  onSelectedTagsChange: (tags: string[]) => void;
  /** 可筛选的全部标签（由当前数据集聚合） */
  availableTags: string[];
  sort: SortField;
  onSortChange: (sort: SortField) => void;
  order: SortOrder;
  onOrderChange: (order: SortOrder) => void;
  sortFields?: SortField[];
  /** 结果计数展示 */
  resultCount?: number;
  /** 会话列表没有标签维度，可隐藏标签筛选 */
  showTagFilter?: boolean;
  className?: string;
}

/**
 * 内容库检索工具条（P0 F16）：关键词 + 标签 + 排序。
 * 参数语义与 openapi SearchQuery 一致（q / tags / sort / order）。
 */
export function LibraryToolbar({
  query,
  onQueryChange,
  placeholder = '搜索名称、描述、标签…（支持中文子串）',
  selectedTags,
  onSelectedTagsChange,
  availableTags,
  sort,
  onSortChange,
  order,
  onOrderChange,
  sortFields = ['updated_at', 'created_at', 'name'],
  resultCount,
  showTagFilter = true,
  className,
}: LibraryToolbarProps) {
  const toggleTag = (tag: string) => {
    onSelectedTagsChange(
      selectedTags.includes(tag) ? selectedTags.filter((t) => t !== tag) : [...selectedTags, tag],
    );
  };

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <div className="relative min-w-[220px] flex-1">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted"
          aria-hidden="true"
        />
        <Input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder={placeholder}
          aria-label="关键词搜索"
          className="pl-8 pr-8"
          maxLength={200}
        />
        {query ? (
          <button
            type="button"
            aria-label="清除关键词"
            onClick={() => onQueryChange('')}
            className="absolute right-2 top-1/2 grid size-5 -translate-y-1/2 place-items-center rounded-xs text-muted motion-fast hover:bg-surface-warm hover:text-fg"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {showTagFilter ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              <Filter className="size-4" aria-hidden="true" />
              标签
              {selectedTags.length > 0 ? (
                <span className="tech-meta text-accent">{selectedTags.length}</span>
              ) : null}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>按标签筛选（同时满足）</DropdownMenuLabel>
            {availableTags.length === 0 ? (
              <div className="flex items-start gap-2 px-2 py-2 text-sm leading-relaxed text-muted">
                <Tags className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                <span>当前还没有任何标签。给角色卡或世界书打上标签后，这里就会出现可筛选项。</span>
              </div>
            ) : (
              availableTags.map((tag) => (
                <DropdownMenuItem
                  key={tag}
                  onSelect={(e) => {
                    e.preventDefault();
                    toggleTag(tag);
                  }}
                  className="justify-between"
                >
                  <span className="truncate">{tag}</span>
                  {selectedTags.includes(tag) ? (
                    <span className="tech-meta text-accent">已选</span>
                  ) : null}
                </DropdownMenuItem>
              ))
            )}
            {selectedTags.length > 0 ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => onSelectedTagsChange([])}>
                  <X className="size-4" aria-hidden="true" />
                  清除全部标签
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}

      <Button
        variant="outline"
        size="icon"
        aria-label={order === 'desc' ? '当前降序，点击切换为升序' : '当前升序，点击切换为降序'}
        onClick={() => onOrderChange(order === 'desc' ? 'asc' : 'desc')}
      >
        {order === 'desc' ? (
          <ArrowDown className="size-4" aria-hidden="true" />
        ) : (
          <ArrowUp className="size-4" aria-hidden="true" />
        )}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="gap-2">
            <ArrowUpDown className="size-4" aria-hidden="true" />
            {SORT_LABELS[sort]}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>排序方式</DropdownMenuLabel>
          {sortFields.map((field) => (
            <DropdownMenuItem key={field} onSelect={() => onSortChange(field)} className="justify-between">
              {SORT_LABELS[field]}
              {sort === field ? <span className="tech-meta text-accent">当前</span> : null}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {typeof resultCount === 'number' ? (
        <span className="tech-meta ml-1" aria-live="polite">
          {resultCount} 项
        </span>
      ) : null}
    </div>
  );
}

/** 已选标签的 chips 行（可逐个移除） */
export function ActiveTagChips({
  tags,
  onRemove,
  className,
}: {
  tags: string[];
  onRemove: (tag: string) => void;
  className?: string;
}) {
  if (tags.length === 0) return null;
  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)}>
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-xs border border-border bg-surface-warm px-1.5 py-0.5 text-xs text-fg-2"
        >
          {tag}
          <button
            type="button"
            aria-label={`移除标签 ${tag}`}
            onClick={() => onRemove(tag)}
            className="grid size-3.5 place-items-center rounded-xs text-muted motion-fast hover:text-fg"
          >
            <X className="size-3" aria-hidden="true" />
          </button>
        </span>
      ))}
    </div>
  );
}
