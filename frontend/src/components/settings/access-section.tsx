import { useQuery } from '@tanstack/react-query';
import { systemApi } from '@/api/client';
import { toast } from '@/stores/ui';
import { useAuthSession, useLogout } from '@/hooks/use-auth';
import { StatTile } from '@/components/common/stat';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SettingsSection } from './section';
import { KeyRound, CircleCheck, TriangleAlert, LogOut, Cpu, Cloud, Images } from '@/components/icons';

/** 访问口令：单用户形态说明 + 本机状态 + 退出登录 */
export function AccessSection() {
  const { data, isLoading, isError } = useAuthSession();
  const logout = useLogout();
  const info = useQuery({ queryKey: ['system', 'info'], queryFn: systemApi.info, retry: false });

  return (
    <SettingsSection
      icon={KeyRound}
      title="访问口令"
      aside={
        isLoading ? (
          <Badge variant="outline">校验中</Badge>
        ) : isError ? (
          <Badge variant="warn">未连后端</Badge>
        ) : data?.authenticated ? (
          <Badge variant="success">已通过校验</Badge>
        ) : (
          <Badge variant="danger">未登录</Badge>
        )
      }
    >
      <p className="text-base leading-relaxed text-muted">
        单用户形态：整台实例由<strong className="font-medium text-fg-2">一个</strong>访问口令保护，没有账号体系。
        口令与签名密钥都在部署机的 <code className="font-mono text-sm">.env</code> 里，改完执行{' '}
        <code className="font-mono text-sm">docker compose up -d --force-recreate</code> 生效。
      </p>

      <ul className="space-y-2 text-sm leading-relaxed text-fg-2">
        <li className="flex items-start gap-2">
          <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden="true" />
          <span>
            口令：环境变量 <code className="font-mono">ACCESS_PASSWORD</code>，建议 12 位以上随机串。留空时服务仍启动但会打印醒目告警。
          </span>
        </li>
        <li className="flex items-start gap-2">
          <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden="true" />
          <span>
            令牌签名密钥：<code className="font-mono">SECRET_KEY</code>，用{' '}
            <code className="font-mono">openssl rand -hex 32</code> 生成。
            <span className="text-muted">泄露等于会话可被伪造。</span>
          </span>
        </li>
        <li className="flex items-start gap-2">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-warn" aria-hidden="true" />
          <span>
            连续错误口令达阈值触发限流（<code className="font-mono">ACCESS_MAX_FAILED</code>，默认 5 次，锁 15 分钟）。
            走纯 HTTP 调试时记得把 <code className="font-mono">SESSION_COOKIE_SECURE</code> 设为 false，否则浏览器不回传 Cookie。
          </span>
        </li>
      </ul>

      {info.data ? (
        <div className="grid gap-2 sm:grid-cols-3">
          <StatTile
            label="版本"
            value={<span className="text-base">{info.data.app_version || '—'}</span>}
            icon={Cpu}
            hint={`会话 schema ${info.data.schema_versions.session}`}
          />
          <StatTile
            label="模型后端"
            value={<span className="text-base">{info.data.llm_provider || '未配置'}</span>}
            tone={info.data.llm_provider ? 'success' : 'warn'}
            icon={Cloud}
            hint={info.data.llm_model || undefined}
          />
          <StatTile
            label="出图"
            value={<span className="text-base">{info.data.image_provider || '未配置'}</span>}
            tone={info.data.image_provider ? 'info' : 'neutral'}
            icon={Images}
            hint={info.data.gpu_available ? 'GPU 可用' : '未检测到 GPU'}
          />
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 border-t border-border-soft pt-4">
        <Button
          variant="outline"
          onClick={() =>
            logout.mutate(undefined, {
              onSuccess: () => toast.show('已退出登录', '需要重新输入访问口令。'),
              onError: () => toast.warn('退出请求失败', '本地会话可能已失效，刷新页面即可。'),
            })
          }
          loading={logout.isPending}
        >
          <LogOut className="size-4" aria-hidden="true" />
          退出登录
        </Button>
        <span className="text-sm text-meta">退出后跳转登录页，本地缓存的会话内容随之清空。</span>
      </div>
    </SettingsSection>
  );
}
