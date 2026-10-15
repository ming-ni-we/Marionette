import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { TagInput } from '@/components/common/tag-input';
import { X, Plus } from '@/components/icons';
import { estimateTokens } from './card-preview';
import type { CardData } from '@/api/types';

export type CardEditMode = 'quick' | 'advanced';

export const CARD_GROUPS = [
  { id: 'base', label: '基础', hint: '名称与标签' },
  { id: 'persona', label: '人设', hint: '描述 / 性格 / 场景' },
  { id: 'dialogue', label: '对话', hint: '开场白与示例' },
  { id: 'advanced', label: '高级', hint: '提示词覆盖 / 作者注' },
] as const;

interface CardFormProps {
  draft: CardData;
  onChange: (patch: Partial<CardData>) => void;
  mode: CardEditMode;
}

/** 角色卡编辑表单：分组折叠 + 术语人话化（直接修正酒馆的术语暴露病灶） */
export function CardForm({ draft, onChange, mode }: CardFormProps) {
  const advancedOpen = mode === 'advanced';

  return (
    <div>
      <div id="card-group-base">
        <GroupSection id="base" title="基础" description="只影响你自己怎么找到这张卡，不进模型的上下文。" defaultOpen>
          <Field
            label="角色名"
            htmlFor="card-name"
            hint="会话里显示的称呼，也是 {{char}} 替换成的名字。"
            accessory={<span className="tech-meta">{draft.name.length} 字</span>}
          >
            <Input
              id="card-name"
              value={draft.name}
              onChange={(e) => onChange({ name: e.target.value })}
              placeholder="例如：苏晚"
              maxLength={60}
            />
          </Field>

          <Field label="标签" htmlFor="card-tags" optional hint="用于内容库筛选，可多个。">
            <TagInput tags={draft.tags} onChange={(tags) => onChange({ tags })} />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="作者" htmlFor="card-creator" optional hint="导出后会写进卡片的 creator 字段。">
              <Input
                id="card-creator"
                value={draft.creator}
                onChange={(e) => onChange({ creator: e.target.value })}
                placeholder="留空则导出时写「未知」"
              />
            </Field>
            <Field label="版本" htmlFor="card-version" optional>
              <Input
                id="card-version"
                value={draft.character_version}
                onChange={(e) => onChange({ character_version: e.target.value })}
                placeholder="1.0"
              />
            </Field>
          </div>
        </GroupSection>
      </div>

      <div id="card-group-persona">
        <GroupSection
          id="persona"
          title="人设"
          description="以下是角色的核心定义，会一直作为设定发给模型——写得越具体，演得越稳。"
          defaultOpen
          summary={<span className="tech-meta">{estimateTokens(draft.description + draft.personality + draft.scenario)} tok</span>}
        >
          <Field
            label="她是谁（描述）"
            htmlFor="card-description"
            hint="身份、外貌、生活状态、说话习惯。这一段是模型理解角色的主依据。"
            accessory={<span className="tech-meta">{estimateTokens(draft.description)} tok</span>}
          >
            <Textarea
              id="card-description"
              value={draft.description}
              onChange={(e) => onChange({ description: e.target.value })}
              placeholder="例如：旧城区「未名书店」的店主，24 岁。留着齐肩短发，说话慢……"
              className="min-h-28"
            />
          </Field>

          <Field
            label="性格要点"
            htmlFor="card-personality"
            optional
            hint="可以只写几个词。模型会拿它约束语气的松紧。"
            accessory={<span className="tech-meta">{estimateTokens(draft.personality)} tok</span>}
          >
            <Textarea
              id="card-personality"
              value={draft.personality}
              onChange={(e) => onChange({ personality: e.target.value })}
              placeholder="例如：安静、专注，不擅长寒暄但记得住每位回头客的口味。"
              className="min-h-20"
            />
          </Field>

          <Field
            label="故事开始时的场景"
            htmlFor="card-scenario"
            optional
            hint="时间、地点、正在发生的事。决定了第一句话从哪儿接。"
            accessory={<span className="tech-meta">{estimateTokens(draft.scenario)} tok</span>}
          >
            <Textarea
              id="card-scenario"
              value={draft.scenario}
              onChange={(e) => onChange({ scenario: e.target.value })}
              placeholder="例如：梅雨季的傍晚，书店快打烊，屋檐滴水敲着铁皮雨棚。"
              className="min-h-20"
            />
          </Field>

          <Field
            label="角色外观"
            htmlFor="card-art-style"
            optional
            hint="配图时该角色的长相特征（发色、服饰、气质）。会和世界观的整体画风叠加，不是覆盖。"
          >
            <Input
              id="card-art-style"
              value={draft.art_style}
              onChange={(e) => onChange({ art_style: e.target.value })}
              placeholder="例如：齐肩短发，米色针织衫，说话时习惯低头"
            />
          </Field>
        </GroupSection>
      </div>

      <div id="card-group-dialogue">
        <GroupSection
          id="dialogue"
          title="对话"
          description="开场白决定第一印象；示例对话决定模型学到什么样的说话节奏。"
          defaultOpen
        >
          <Field
            label="开场白"
            htmlFor="card-first-mes"
            hint="会话开始时角色说的第一段话。用换行分段会更有画面感。"
            accessory={<span className="tech-meta">{estimateTokens(draft.first_mes)} tok</span>}
          >
            <Textarea
              id="card-first-mes"
              value={draft.first_mes}
              onChange={(e) => onChange({ first_mes: e.target.value })}
              placeholder={'风铃响了一声。她从柜台后抬起头。\n\n「外面的雨比预报的大。」'}
              className="min-h-28"
            />
          </Field>

          <Field
            label="备选开场白"
            htmlFor="card-alt-greetings"
            optional
            hint="想试不同开局时用；开会话时可以从中挑一条。"
          >
            <div className="space-y-2">
              {draft.alternate_greetings.map((g, i) => (
                <div key={i} className="flex items-start gap-2">
                  <Textarea
                    value={g}
                    onChange={(e) => {
                      const next = [...draft.alternate_greetings];
                      next[i] = e.target.value;
                      onChange({ alternate_greetings: next });
                    }}
                    aria-label={`第 ${i + 1} 条备选开场白`}
                    className="min-h-16"
                  />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`删除第 ${i + 1} 条备选开场白`}
                    onClick={() =>
                      onChange({ alternate_greetings: draft.alternate_greetings.filter((_, k) => k !== i) })
                    }
                  >
                    <X className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() => onChange({ alternate_greetings: [...draft.alternate_greetings, ''] })}
              >
                <Plus className="size-4" aria-hidden="true" />
                加一条备选开场白
              </Button>
            </div>
          </Field>

          <Field
            label="示例对话"
            htmlFor="card-example"
            optional
            hint="格式：{{user}}: … 与 {{char}}: … 各占一行，成对出现。模型会学到这种节奏。"
            accessory={<span className="tech-meta">{estimateTokens(draft.mes_example)} tok</span>}
          >
            <Textarea
              id="card-example"
              value={draft.mes_example}
              onChange={(e) => onChange({ mes_example: e.target.value })}
              placeholder={'{{user}}: 你这儿有讲老城区的书吗？\n{{char}}: 她想了想，从第三排抽出一本封面磨白的册子。'}
              className="min-h-24 font-mono text-sm"
            />
          </Field>
        </GroupSection>
      </div>

      <div id="card-group-advanced">
        <GroupSection
          id="advanced"
          title="高级"
          description="这些会直接改动发给模型的结构。不确定就先留空——留空会走预设里的默认值。"
          defaultOpen={advancedOpen}
          summary={advancedOpen ? undefined : <span className="tech-meta">通常留空</span>}
        >
          <Field
            label="系统提示词覆盖"
            htmlFor="card-system"
            optional
            hint="不填就用预设里的系统提示词。只有这张卡需要特立独行的规则时才改。"
          >
            <Textarea
              id="card-system"
              value={draft.system_prompt}
              onChange={(e) => onChange({ system_prompt: e.target.value })}
              placeholder="留空 = 使用预设中的系统提示词"
              className="min-h-20 font-mono text-sm"
            />
          </Field>

          <Field
            label="历史后指令"
            htmlFor="card-post-history"
            optional
            hint="放在所有对话之后，用来强约束语气或禁忌（比系统提示更靠后，通常更管得住）。"
          >
            <Textarea
              id="card-post-history"
              value={draft.post_history_instructions}
              onChange={(e) => onChange({ post_history_instructions: e.target.value })}
              placeholder="例如：保持克制、生活化的语感；不主动引入超自然元素。"
              className="min-h-20"
            />
          </Field>

          <Field
            label="作者注"
            htmlFor="card-notes"
            optional
            hint="不进上下文，纯粹写给你自己看——适合记录这张卡该怎么用。"
          >
            <Textarea
              id="card-notes"
              value={draft.creator_notes}
              onChange={(e) => onChange({ creator_notes: e.target.value })}
              placeholder="例如：适合慢热日常向。开场即雨天书店，前 3 轮不建议推进剧情。"
              className="min-h-20"
            />
          </Field>
        </GroupSection>
      </div>
    </div>
  );
}
