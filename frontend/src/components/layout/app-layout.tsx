import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Rail } from './rail';
import { Folder, MessageSquare, Images, Settings } from '@/components/icons';

const MOBILE_ITEMS = [
  { to: '/', label: '内容库', icon: Folder, end: true },
  { to: '/sessions', label: '会话', icon: MessageSquare, end: false },
  { to: '/assets', label: '素材', icon: Images, end: false },
  { to: '/settings', label: '设置', icon: Settings, end: false },
];

/**
 * 创作端主布局：左侧 rail + 内容区。
 * <768px 时 rail 收为底部 TabBar（见 docs/03-uiux.md §7.1）。
 */
export function AppLayout() {
  const location = useLocation();
  return (
    <div className="flex min-h-dvh bg-bg">
      <div className="hidden md:block">
        <Rail />
      </div>
      <main className="min-w-0 flex-1 pb-14 md:pb-0">
        <Outlet />
      </main>

      {/* 移动端底部 TabBar */}
      <nav
        aria-label="移动端主导航"
        className="fixed inset-x-0 bottom-0 z-dock flex items-stretch border-t border-border bg-surface md:hidden"
      >
        {MOBILE_ITEMS.map(({ to, label, icon: Icon, end }) => {
          const active = end ? location.pathname === to : location.pathname.startsWith(to);
          return (
            <NavLink
              key={to}
              to={to}
              className={cn(
                'flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 text-xs motion-fast',
                active ? 'text-accent' : 'text-muted',
              )}
            >
              <Icon className="size-5" aria-hidden="true" />
              {label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
