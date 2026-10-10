import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { UserRoundPlus, BookPlus, SlidersHorizontal, MessageSquare, Keyboard } from '@/components/icons';

const ENTRIES = [
  {
    to: '/cards/new',
    label: '新建角色卡',
    desc: '从零写一个人设，右侧有实时气泡预览',
    Icon: UserRoundPlus,
  },
  {
    to: '/worldbooks/new',
    label: '新建世界书',
    desc: '关键词触发的设定条目，附带命中测试',
    Icon: BookPlus,
  },
  {
    to: '/presets/new',
    label: '新建预设',
    desc: '系统提示词与采样参数，决定模型的说话方式',
    Icon: SlidersHorizontal,
  },
  {
    to: '/sessions',
    label: '开一场会话',
    desc: '挑一张卡就能直接开聊',
    Icon: MessageSquare,
  },
];

/** 工作台右侧「快速开始」面板（docs/03-uiux.md §7.1） */
export function QuickStartPanel({ className }: { className?: string }) {
  return (
    <section aria-labelledby="quick-start-title" className={cn('space-y-2', className)}>
      <h2 id="quick-start-title" className="label-caps px-1">
        快速开始
      </h2>
      <ul className="space-y-1.5">
        {ENTRIES.map(({ to, label, desc, Icon }) => (
          <li key={to}>
            <Link
              to={to}
              className="flex items-start gap-2.5 rounded-md border border-border bg-surface px-3 py-2.5 motion-fast hover:border-border-strong hover:bg-surface-raised"
            >
              <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-sm border border-border bg-surface-warm text-muted">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block text-base font-medium text-fg">{label}</span>
                <span className="mt-0.5 block text-xs leading-relaxed text-muted">{desc}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <div className="rounded-md border border-border bg-surface px-3 py-2.5">
        <h3 className="flex items-center gap-1.5 label-caps">
          <Keyboard className="size-3.5" aria-hidden="true" />
          快捷键
        </h3>
        <dl className="mt-1.5 space-y-1 text-xs text-muted">
          <div className="flex items-center justify-between gap-2">
            <dt>搜索当前列表</dt>
            <dd className="font-mono text-meta">/</dd>
          </div>
          <div className="flex items-center justify-between gap-2">
            <dt>沉浸模式开关</dt>
            <dd className="font-mono text-meta">Esc</dd>
          </div>
          <div className="flex items-center justify-between gap-2">
            <dt>发送消息</dt>
            <dd className="font-mono text-meta">Enter</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
