import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { onboardingApi } from '@/api/client';
import { toast } from '@/stores/ui';
import { Button } from '@/components/ui/button';
import { CirclePlus, CircleCheck, ArrowLeft } from '@/components/icons';

/** 步骤 3：安装示例内容（3–5 张现代日常向示例卡，各带世界书与预设） */
export function SamplesStep({ onBack }: { onBack: () => void }) {
  const navigate = useNavigate();

  const installSamples = useMutation({
    mutationFn: () => onboardingApi.installSamples(),
    onSuccess: (res) => {
      toast.success(`已安装 ${res.card_ids.length} 张示例卡`, '内容库里现在有可以立刻开聊的角色卡了。');
      navigate('/');
    },
    onError: () => toast.danger('安装失败', '后端没有返回结果，稍后可在内容库重试。'),
  });

  return (
    <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
      <h2 className="title-section flex items-center gap-2 text-fg">
        <CirclePlus className="size-4 text-muted" aria-hidden="true" />
        安装示例内容
      </h2>
      <p className="text-base leading-relaxed text-muted">
        安装 3–5 张「现代日常向」示例卡，每张都自带一本世界书与一套默认预设。装完之后，
        你可以直接点开一张卡开会话——不用先自己写设定。
      </p>
      <ul className="space-y-1.5 text-sm leading-relaxed text-fg-2">
        <li className="flex items-start gap-2">
          <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden="true" />
          示例卡可以随时删除、复制、改写成你自己的角色
        </li>
        <li className="flex items-start gap-2">
          <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden="true" />
          导入 SillyTavern 卡片也走同一套 schema，字段不会丢
        </li>
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          上一步
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="ghost" asChild>
            <Link to="/">我自己建，直接去内容库</Link>
          </Button>
          <Button variant="primary" onClick={() => installSamples.mutate()} loading={installSamples.isPending}>
            <CirclePlus className="size-4" aria-hidden="true" />
            安装示例内容
          </Button>
        </div>
      </div>
    </section>
  );
}
