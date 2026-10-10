import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/stores/ui';
import { Hint } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import {
  Folder,
  MessageSquare,
  Images,
  Settings,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Sun,
  Moon,
} from '@/components/icons';
import { InstanceStatus } from './instance-status';

interface RailItem {
  to: string;
  label: string;
  icon: typeof Folder;
  end?: boolean;
}

const NAV_ITEMS: RailItem[] = [
  { to: '/', label: '内容库', icon: Folder, end: true },
  { to: '/sessions', label: '会话', icon: MessageSquare },
  { to: '/assets', label: '素材', icon: Images },
  { to: '/settings', label: '设置', icon: Settings },
];

/**
 * 全局导航 rail（64px）。
 * 单机无账号 → 底部用「本机状态」位替代账号位（模型连接 / 后端 / 存储）。
 */
export function Rail() {
  const railExpanded = useUiStore((s) => s.railExpanded);
  const toggleRail = useUiStore((s) => s.toggleRail);
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const location = useLocation();

  return (
    <aside
      className={cn(
        'sticky top-0 flex h-dvh shrink-0 flex-col border-r border-border bg-surface-sunken',
        railExpanded ? 'w-56' : 'w-[var(--rail-width)]',
      )}
    >
      {/* 品牌区 */}
      <div className="flex h-14 items-center gap-2.5 px-4">
        <span className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-surface text-accent">
          <Network className="size-4" aria-hidden="true" />
        </span>
        {railExpanded ? (
          <span className="min-w-0">
            <span className="block truncate text-md font-semibold tracking-tight text-fg">提线</span>
            <span className="block truncate text-xs text-meta">Marionette</span>
          </span>
        ) : null}
      </div>

      {/* 主导航 */}
      <nav aria-label="主导航" className="flex flex-1 flex-col gap-0.5 px-2 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => {
          const active = end ? location.pathname === to : location.pathname.startsWith(to);
          const link = (
            <NavLink
              key={to}
              to={to}
              aria-label={label}
              className={cn(
                'flex h-9 items-center gap-2.5 rounded-sm px-2.5 text-base motion-fast',
                railExpanded ? '' : 'justify-center',
                active
                  ? 'bg-accent-subtle text-accent'
                  : 'text-fg-2 hover:bg-surface-warm hover:text-fg',
              )}
            >
              <Icon className="size-5 shrink-0" aria-hidden="true" />
              {railExpanded ? <span className="truncate">{label}</span> : null}
            </NavLink>
          );
          return railExpanded ? (
            link
          ) : (
            <Hint key={to} label={label} side="right">
              {link}
            </Hint>
          );
        })}
      </nav>

      {/* 本机状态位（替代账号位） */}
      <div className="border-t border-border-soft p-2">
        <InstanceStatus expanded={railExpanded} />
      </div>

      {/* 底部控件：主题 + rail 折叠 */}
      <div className="flex items-center gap-1 border-t border-border-soft p-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'}
          onClick={toggleTheme}
        >
          {theme === 'dark' ? (
            <Sun className="size-4" aria-hidden="true" />
          ) : (
            <Moon className="size-4" aria-hidden="true" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={railExpanded ? '收起侧栏' : '展开侧栏'}
          onClick={toggleRail}
          className={cn(!railExpanded && 'mx-auto')}
        >
          {railExpanded ? (
            <PanelLeftClose className="size-4" aria-hidden="true" />
          ) : (
            <PanelLeftOpen className="size-4" aria-hidden="true" />
          )}
        </Button>
      </div>
    </aside>
  );
}
