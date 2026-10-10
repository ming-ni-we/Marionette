import { Link, useLocation } from 'react-router-dom';
import { EmptyState } from '@/components/common/empty-state';
import { Button } from '@/components/ui/button';
import { Compass, Folder, ArrowLeft } from '@/components/icons';

/** 404：仍然给"能直接照做"的出口，不留空白页（AC-16 精神） */
export function NotFoundPage() {
  const location = useLocation();
  const path = location.pathname.replace(/^\//, '');
  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <EmptyState
        icon={Compass}
        title="这个地址没有对应的页面"
        description={`走到 /${path} 时没有匹配到路由。可能是链接过期，或者手输时打错了。`}
        actions={
          <>
            <Button variant="primary" asChild>
              <Link to="/">
                <Folder className="size-4" aria-hidden="true" />
                回到内容库
              </Link>
            </Button>
            <Button variant="ghost" asChild>
              <Link to="/sessions">
                <ArrowLeft className="size-4" aria-hidden="true" />
                去看会话
              </Link>
            </Button>
          </>
        }
        hint={
          <span>
            常用入口：<span className="font-mono text-sm">/</span> 内容库 ·{' '}
            <span className="font-mono text-sm">/sessions</span> 会话 ·{' '}
            <span className="font-mono text-sm">/assets</span> 素材 ·{' '}
            <span className="font-mono text-sm">/settings</span> 设置
          </span>
        }
      />
    </div>
  );
}
