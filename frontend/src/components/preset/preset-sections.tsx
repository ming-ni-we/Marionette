import { cn } from '@/lib/utils';
import type { PresetData } from '@/api/types';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { RangeField } from './range-field';

export interface SectionProps {
  draft: PresetData;
  patch: (p: Partial<PresetData>) => void;
}

export function BaseInfoSection({ draft, patch }: SectionProps) {
  return (
    <GroupSection id="preset-base" title="基本信息" defaultOpen>
      <Field label="预设名称" htmlFor="preset-name">
        <Input
          id="preset-name"
          value={draft.name}
          onChange={(e) => patch({ name: e.target.value })}
          placeholder="例如：日常向 · 稳"
        />
      </Field>
      <Field label="用途说明" htmlFor="preset-desc" optional>
        <Input
          id="preset-desc"
          value={draft.description}
          onChange={(e) => patch({ description: e.target.value })}
          placeholder="例如：慢节奏日常会话，减少跑题。"
        />
      </Field>
    </GroupSection>
  );
}

export function PromptSection({ draft, patch }: SectionProps) {
  const patchTemplate = (p: Partial<PresetData['prompt_template']>) =>
    patch({ prompt_template: { ...draft.prompt_template, ...p } });
  return (
    <GroupSection
      id="preset-prompt"
      title="系统提示词"
      description="这是模型每轮都会先读到的一段。{{char}}、{{user}}、{{persona}} 会被自动替换。"
      defaultOpen
    >
      <Field label="系统提示词" htmlFor="preset-system" hint="写「你是谁、怎么演」，不写具体剧情。">
        <Textarea
          id="preset-system"
          value={draft.prompt_template.system}
          onChange={(e) => patchTemplate({ system: e.target.value })}
          placeholder="你正在扮演 {{char}}。以第一人称沉浸式回应……"
          className="min-h-28"
        />
      </Field>
      <Field label="补充指令" htmlFor="preset-instruction" optional hint="放在系统提示词之后的通用约束。">
        <Textarea
          id="preset-instruction"
          value={draft.prompt_template.instruction}
          onChange={(e) => patchTemplate({ instruction: e.target.value })}
          className="min-h-16"
        />
      </Field>
    </GroupSection>
  );
}

export function SamplingSection({ draft, patch }: SectionProps) {
  const p = (v: Partial<PresetData['sampling']>) => patch({ sampling: { ...draft.sampling, ...v } });
  return (
    <GroupSection
      id="preset-sampling"
      title="采样参数"
      description="控制模型的「随机程度」。不确定就保持默认——这些默认档已在大多数模型上试过。"
      defaultOpen={false}
      summary={<span className="tech-meta">temp {draft.sampling.temperature}</span>}
    >
      <RangeField
        id="sampling-temp"
        label="温度 Temperature"
        hint="越大越发散、越有惊喜，也越容易跑题。日常向建议 0.7–0.9。"
        value={draft.sampling.temperature}
        min={0}
        max={2}
        step={0.01}
        onChange={(v) => p({ temperature: v })}
      />
      <RangeField
        id="sampling-top-p"
        label="Top P"
        hint="只从累计概率前 P 的候选里挑词。一般和温度二选一调。"
        value={draft.sampling.top_p}
        min={0}
        max={1}
        step={0.01}
        onChange={(v) => p({ top_p: v })}
      />
      <RangeField
        id="sampling-top-k"
        label="Top K"
        hint="只从概率最高的 K 个词里挑。0 表示不限制。"
        value={draft.sampling.top_k}
        min={0}
        max={200}
        step={1}
        onChange={(v) => p({ top_k: v })}
      />
      <RangeField
        id="sampling-rep"
        label="重复惩罚"
        hint="调大能减少复读，调太大句子会变得别扭。"
        value={draft.sampling.repetition_penalty}
        min={1}
        max={1.5}
        step={0.01}
        onChange={(v) => p({ repetition_penalty: v })}
      />
      <Field label="单条回复上限（token）" htmlFor="sampling-max" hint="太短容易话没说完，太长会拖慢生成。">
        <Input
          id="sampling-max"
          type="number"
          value={draft.sampling.max_tokens}
          min={64}
          max={8192}
          step={64}
          onChange={(e) => p({ max_tokens: Number(e.target.value) })}
          className="font-mono tabular-nums"
        />
      </Field>
    </GroupSection>
  );
}

export function BudgetSection({ draft, patch }: SectionProps) {
  const b = draft.context_budget;
  const pb = (v: Partial<PresetData['context_budget']>) =>
    patch({ context_budget: { ...draft.context_budget, ...v } });
  const sum = b.character_pct + b.world_info_pct + b.memory_pct + b.vector_recall_pct + b.history_pct;
  return (
    <GroupSection
      id="preset-budget"
      title="上下文预算"
      description="把有限的上下文额度分配给不同内容。超出预算时会按预设顺序裁剪，并给出截断提示。"
      defaultOpen={false}
      summary={<span className="tech-meta">{sum}% 已分配</span>}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="最大上下文（token）" htmlFor="budget-max" hint="要和模型自身的窗口匹配。">
          <Input
            id="budget-max"
            type="number"
            value={b.max_context_tokens}
            min={1024}
            max={131072}
            step={1024}
            onChange={(e) => pb({ max_context_tokens: Number(e.target.value) })}
            className="font-mono tabular-nums"
          />
        </Field>
        <Field label="为输出预留（token）" htmlFor="budget-reserve" hint="保证模型有生成空间。">
          <Input
            id="budget-reserve"
            type="number"
            value={b.reserve_for_output}
            min={128}
            max={8192}
            step={128}
            onChange={(e) => pb({ reserve_for_output: Number(e.target.value) })}
            className="font-mono tabular-nums"
          />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <RangeField id="pct-char" label="角色定义占比" hint="" value={b.character_pct} min={0} max={100} step={1} onChange={(v) => pb({ character_pct: v })} />
        <RangeField id="pct-wb" label="世界书占比" hint="" value={b.world_info_pct} min={0} max={100} step={1} onChange={(v) => pb({ world_info_pct: v })} />
        <RangeField id="pct-mem" label="长期记忆占比" hint="" value={b.memory_pct} min={0} max={100} step={1} onChange={(v) => pb({ memory_pct: v })} />
        <RangeField id="pct-hist" label="历史消息占比" hint="" value={b.history_pct} min={0} max={100} step={1} onChange={(v) => pb({ history_pct: v })} />
      </div>
      <p className={cn('text-sm leading-relaxed', sum > 100 ? 'text-danger' : 'text-meta')}>
        当前合计 {sum}%
        {sum > 100
          ? ' —— 超过 100%，实际会按比例压缩，建议调回 100% 以内。'
          : '（各段占比之和，留出的余量作为缓冲）。'}
      </p>
    </GroupSection>
  );
}

export function MemorySection({ draft, patch }: SectionProps) {
  const pm = (v: Partial<PresetData['memory']>) => patch({ memory: { ...draft.memory, ...v } });
  return (
    <GroupSection
      id="preset-memory"
      title="记忆与摘要"
      description="长会话靠它不会失忆：定期把旧对话压成摘要，并抽取关键事实长期保存。"
      defaultOpen={false}
      summary={<span className="tech-meta">每 {draft.memory.summarize_every_n_turns} 轮</span>}
    >
      <Field label="每几轮做一次摘要" htmlFor="mem-every" hint="太频繁会打断节奏，太稀疏会记不住伏笔。">
        <Input
          id="mem-every"
          type="number"
          value={draft.memory.summarize_every_n_turns}
          min={2}
          max={100}
          onChange={(e) => pm({ summarize_every_n_turns: Number(e.target.value) })}
          className="font-mono tabular-nums"
        />
      </Field>
      <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-warm px-3 py-2.5">
        <div>
          <div className="text-base text-fg">抽取关键事实</div>
          <p className="mt-0.5 text-xs leading-relaxed text-muted">
            把「玩家名字」「已获得物品」这类信息结构化成事实表，需要时优先召回。
          </p>
        </div>
        <Switch
          checked={draft.memory.extract_facts}
          onCheckedChange={(v) => pm({ extract_facts: v })}
          label="抽取关键事实"
        />
      </div>
    </GroupSection>
  );
}

export function ImageHookSection({ draft, patch }: SectionProps) {
  const ph = (v: Partial<PresetData['image_hook']>) =>
    patch({ image_hook: { ...draft.image_hook, ...v } });
  return (
    <GroupSection
      id="preset-image"
      title="出图钩子"
      description="配置了图像后端后，可以在会话里按节奏自动出图，并归档进角色图集。"
      defaultOpen={false}
      summary={<span className="tech-meta">{draft.image_hook.enabled ? '已开启' : '关闭'}</span>}
    >
      <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-warm px-3 py-2.5">
        <div>
          <div className="text-base text-fg">启用出图</div>
          <p className="mt-0.5 text-xs leading-relaxed text-muted">
            v1 使用云端图像 API（自备 Key）。出图与对话互不阻塞。
          </p>
        </div>
        <Switch checked={draft.image_hook.enabled} onCheckedChange={(v) => ph({ enabled: v })} label="启用出图钩子" />
      </div>
      {draft.image_hook.enabled ? (
        <Field label="触发时机" htmlFor="img-mode" hint="手动最可控；按轮数适合长期连载。">
          <Select
            value={draft.image_hook.mode}
            onValueChange={(v) => ph({ mode: v as PresetData['image_hook']['mode'] })}
          >
            <SelectTrigger id="img-mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="manual">手动触发</SelectItem>
              <SelectItem value="every_n_turns">每 N 轮自动出图</SelectItem>
              <SelectItem value="on_scene_change">场景切换时出图</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      ) : null}
    </GroupSection>
  );
}
