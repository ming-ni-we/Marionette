import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLogin } from '@/hooks/use-auth';
import { ApiError } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Network, Eye, EyeOff, Lock, TriangleAlert } from '@/components/icons';

/**
 * 单用户口令登录页（SPEC §7 附加页 / AC-02、AC-03）。
 * 不是账号体系：只有一道访问门。口令来自服务器 .env 的 ACCESS_PASSWORD。
 */
export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    login.mutate(password, {
      onSuccess: () => navigate('/', { replace: true }),
      onError: (err) => {
        if (err instanceof ApiError && err.status === 429) {
          setError('错误次数过多，已临时限速。请等一分钟再试。');
        } else if (err instanceof ApiError && err.status === 401) {
          setError('口令不对。口令是服务器 .env 里 ACCESS_PASSWORD 的值。');
        } else {
          setError('连不上后端实例。确认 docker compose 已经起来，再试一次。');
        }
      },
    });
  };

  return (
    <main className="grid min-h-dvh place-items-center bg-bg px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-md border border-border bg-surface text-accent">
            <Network className="size-4" aria-hidden="true" />
          </span>
          <div>
            <div className="text-md font-semibold tracking-tight text-fg">提线</div>
            <div className="text-xs text-meta">你的私有角色扮演实例</div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-border bg-surface p-5">
          <div className="space-y-1.5">
            <Label htmlFor="access-password">访问口令</Label>
            <div className="relative">
              <Lock
                className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted"
                aria-hidden="true"
              />
              <Input
                id="access-password"
                type={reveal ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                autoFocus
                required
                placeholder="输入 ACCESS_PASSWORD"
                className="pl-8 pr-9"
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? 'login-error' : undefined}
              />
              <button
                type="button"
                onClick={() => setReveal((v) => !v)}
                aria-label={reveal ? '隐藏口令' : '显示口令'}
                className="absolute right-2 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-xs text-muted motion-fast hover:text-fg"
              >
                {reveal ? (
                  <EyeOff className="size-4" aria-hidden="true" />
                ) : (
                  <Eye className="size-4" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          {error ? (
            <p
              id="login-error"
              role="alert"
              className="flex items-start gap-1.5 rounded-sm border border-border bg-danger-subtle px-2.5 py-2 text-sm leading-relaxed text-danger"
            >
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {error}
            </p>
          ) : null}

          <Button
            type="submit"
            variant="primary"
            className="w-full"
            loading={login.isPending}
            disabled={password.length === 0}
          >
            进入工作台
          </Button>

          <p className="text-xs leading-relaxed text-meta">
            这是私有实例，没有注册、没有找回密码。口令在服务器的 <code className="font-mono">.env</code>{' '}
            文件里修改 <code className="font-mono">ACCESS_PASSWORD</code> 后重启容器即可。
          </p>
        </form>
      </div>
    </main>
  );
}
