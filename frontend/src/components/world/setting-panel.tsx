import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { StringListField } from './string-list-field';
import type { WorldSetting } from '@/api/types';

/**
 * 世界观核心设定。
 *
 * 这一块直接决定导演**每一轮**都看得到什么（`context_assembler` 的 story_state 段
 * 永不裁剪），所以措辞比数量重要：`rules` 是硬约束，`summary` 是一句话总览。
 */
export function WorldSettingPanel({
  setting,
  onChange,
}: {
  setting: WorldSetting;
  onChange: (patch: Partial<WorldSetting>) => void;
}) {
  return (
    <div>
      <GroupSection
        id="world-setting"
        title="时空与基调"
        description="给导演定调子。这些字段会出现在每一轮的上下文里，写得越具体，角色越不容易跑偏。"
        defaultOpen
      >
        <Field
          label="时代背景"
          htmlFor="world-era"
          hint="例如：架空晚清 · 蒸汽与符咒并存。"
        >
          <Input
            id="world-era"
            value={setting.era ?? ''}
            onChange={(e) => onChange({ era: e.target.value })}
            placeholder="例如：近未来的沿海旧城区"
          />
        </Field>

        <Field
          label="氛围基调"
          htmlFor="world-tone"
          hint="决定旁白与台词的温度：冷硬 / 温暖 / 悬疑 / 荒诞。"
        >
          <Input
            id="world-tone"
            value={setting.tone ?? ''}
            onChange={(e) => onChange({ tone: e.target.value })}
            placeholder="例如：潮湿、压抑，但偶尔有微光"
          />
        </Field>

        <Field
          label="一句话总览"
          htmlFor="world-summary"
          hint="如果只能给模型留一句话，就留这句。它同时是新建剧情会话时的场景摘要。"
        >
          <Textarea
            id="world-summary"
            rows={3}
            value={setting.summary ?? ''}
            onChange={(e) => onChange({ summary: e.target.value })}
            placeholder="例如：旧城区即将拆迁，各方势力都想在最后一个月里拿走属于自己的东西。"
          />
        </Field>

        <Field
          label="画面风格"
          htmlFor="world-art-style"
          optional
          hint="配图用的整体画风。留空则按下方「标签」自动推断（如含「二次元」→ 日式动画风，「悬疑」→ 写实电影感）。"
        >
          <Input
            id="world-art-style"
            value={setting.art_style ?? ''}
            onChange={(e) => onChange({ art_style: e.target.value })}
            placeholder="例如：日式动画赛璐璐风格，明快高饱和配色"
          />
        </Field>
      </GroupSection>

      <GroupSection
        id="world-places-rules"
        title="地点与规则"
        description="规则是硬约束——导演被要求遵守它们。写「没有超自然力量」比写「要真实」有用得多。"
        defaultOpen
      >
        <StringListField
          id="world-locations"
          label="核心地点"
          hint="故事会反复回到的地方。至少写一个，否则行动建议里「移动」会无处可去。"
          placeholder="例如：未名书店"
          values={setting.locations ?? []}
          onChange={(locations) => onChange({ locations })}
          addLabel="添加地点"
        />

        <StringListField
          id="world-rules"
          label="世界规则"
          hint="物理/社会层面的铁律。一句话一条，用肯定句写「是什么」而不是「不要什么」。"
          placeholder="例如：没有超自然力量，一切伤都要时间愈合"
          values={setting.rules ?? []}
          onChange={(rules) => onChange({ rules })}
          addLabel="添加规则"
        />
      </GroupSection>
    </div>
  );
}
