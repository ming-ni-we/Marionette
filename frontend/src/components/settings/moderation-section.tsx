import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { configApi } from '@/api/client';
import type { ModerationConfig } from '@/api/types';
import { toast } from '@/stores/ui';
import { Field } from '@/components/common/field';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ControlRow, SettingsSection } from './section';
import { DEFAULT_MODERATION } from './providers';
import { ShieldCheck, Info, TriangleAlert } from '@/components/icons';

/**
 * 内容审核层：4 个开关 + 违规词表 + 「标记 AI 生成」。
 * AC-12：关闭总开关必须走风险确认，绝不静默关闭。
 */
export function ModerationSection() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['config', 'moderation'],
    queryFn: configApi.getModeration,
    retry: false,
  });

  const [draft, setDraft] = useState<ModerationConfig>(DEFAULT_MODERATION);
  const [wordsText, setWordsText] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    if (!data) return;
    setDraft(data);
    setWordsText(data.rules.blocked_words.join('\n'));
  }, [data]);

  useEffect(() => {
    if (!isLoading && !data) setOffline(true);
  }, [isLoading, data]);

  const save = useMutation({
    mutationFn: (input: ModerationConfig) => configApi.setModeration(input),
    onSuccess: () => {
      toast.success('审核层配置已保存', '输入/输出双端即时按新规则生效。');
      void qc.invalidateQueries({ queryKey: ['config', 'moderation'] });
      void qc.invalidateQueries({ queryKey: ['system', 'info'] });
    },
    onError: () => toast.danger('保存失败', '后端拒绝了这份配置，稍后重试。'),
  });

  const persist = (next: ModerationConfig) => {
    setDraft(next);
    if (offline) {
      toast.show('已保留在本地', '当前未连后端，配置仅存在于本页草稿中。');
      return;
    }
    save.mutate(next);
  };

  const toggleEnabled = (enabled: boolean) => {
    if (enabled) persist({ ...draft, enabled: true });
    else setConfirmOpen(true); // AC-12
  };

  const busy = save.isPending;

  return (
    <SettingsSection
      icon={ShieldCheck}
      title="内容审核层"
      aside={draft.enabled ? <Badge variant="success">已开启</Badge> : <Badge variant="warn">已关闭</Badge>}
    >
      <p className="text-base leading-relaxed text-muted">
        输入/输出双端过滤。开启时，命中违规规则的输入
        <strong className="font-medium text-fg-2">必须</strong>被拦截并给中性提示、不产生模型调用。
        这是合规前置条件——关闭前会先让你确认风险。
      </p>

      <div className="divide-y divide-border-soft rounded-md border border-border">
        <ControlRow
          label="审核层总开关"
          hint="关掉后输入/输出都不再过滤（需完成风险确认）。"
          checked={draft.enabled}
          onCheckedChange={toggleEnabled}
          disabled={busy}
        />
        <ControlRow
          label="检查输入"
          hint="用户发出的内容先过一遍词表，命中则拦截、不调用模型。"
          checked={draft.check_input}
          onCheckedChange={(v) => persist({ ...draft, check_input: v })}
          disabled={!draft.enabled || busy}
        />
        <ControlRow
          label="检查输出"
          hint="模型生成的内容在落库前再过一遍，命中则替换为中性提示。"
          checked={draft.check_output}
          onCheckedChange={(v) => persist({ ...draft, check_output: v })}
          disabled={!draft.enabled || busy}
        />
        <ControlRow
          label="命中即拦截"
          hint="命中违规词时直接阻断；关掉则只是标记、不阻断（不推荐）。"
          checked={draft.rules.block_on_match}
          onCheckedChange={(v) => persist({ ...draft, rules: { ...draft.rules, block_on_match: v } })}
          disabled={!draft.enabled || busy}
        />
      </div>

      <Field
        label="违规词表"
        htmlFor="set-words"
        hint="一行一个词。中文按子串匹配（pg_trgm），命中即触发上面「命中即拦截」的处理。"
        accessory={
          <span className="tech-meta">{wordsText.split('\n').filter((w) => w.trim()).length} 词</span>
        }
      >
        <Textarea
          id="set-words"
          value={wordsText}
          onChange={(e) => setWordsText(e.target.value)}
          onBlur={() =>
            persist({
              ...draft,
              rules: {
                ...draft.rules,
                blocked_words: wordsText
                  .split('\n')
                  .map((w) => w.trim())
                  .filter(Boolean),
              },
            })
          }
          rows={5}
          placeholder={'每行一个词\n例如：\n违禁词示例一\n违禁词示例二'}
          className="font-mono text-sm"
          disabled={!draft.enabled}
        />
      </Field>

      <ControlRow
        label="标记 AI 生成内容"
        hint="开启后，模型生成的消息会带「AI 生成」标记，便于你回看时区分。"
        checked={draft.rules.label_ai_generated}
        onCheckedChange={(v) => persist({ ...draft, rules: { ...draft.rules, label_ai_generated: v } })}
        disabled={!draft.enabled || busy}
        boxed
      />

      {offline ? (
        <p className="flex items-start gap-1.5 text-sm leading-relaxed text-warn">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          未能读取服务端配置，当前为本页草稿。接上后端后重进本页即可加载真实配置。
        </p>
      ) : null}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <TriangleAlert className="size-4 text-warn" aria-hidden="true" />
              确认关闭内容审核层？
            </DialogTitle>
            <DialogDescription>
              关闭后，本实例的输入与输出将<strong className="font-medium text-fg-2">不再经过任何过滤</strong>，
              命中违规内容也不会被拦截。若这台实例可能被他人访问，请保持开启。
            </DialogDescription>
          </DialogHeader>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            你可以随时在本页重新开启——开启后立即恢复双端过滤。
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              取消，保持开启
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setConfirmOpen(false);
                persist({ ...draft, enabled: false });
              }}
            >
              我已了解风险，仍要关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SettingsSection>
  );
}
