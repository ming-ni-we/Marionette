import { Textarea } from '@/components/ui/textarea';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';

/**
 * 序幕文本。
 *
 * 新建剧情会话时，后端 `OpeningSvc` 会优先让模型基于世界观**现场生成**序幕；
 * 这里写的内容作为**兜底底本**（模型不可用时直接用），也会作为生成的参考。
 * 所以它不是「必须写好」的字段，而是「万一模型挂了，故事也不至于空白」的保险。
 */
export function WorldOpeningPanel({
  opening,
  onChange,
}: {
  opening: string;
  onChange: (v: string) => void;
}) {
  const chars = opening.length;
  return (
    <GroupSection
      id="world-opening"
      title="开场序幕"
      description="剧情开始时第一段旁白。留空也行——系统会让 AI 依据上面的设定现写一段。"
      defaultOpen={false}
    >
      <Field
        label="序幕文本"
        htmlFor="world-opening"
        optional
        hint="用旁白的口吻写场景与氛围，不要写角色台词（台词留给导演安排）。"
        accessory={<span className="tech-meta">{chars} 字</span>}
      >
        <Textarea
          id="world-opening"
          rows={8}
          value={opening}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            '例如：\n雨下了三天。旧城区的墙皮泡得发胀，像随时会掉下来一层。\n你把伞收在门口，未名书店的灯还亮着——但今天挂着的招牌被翻了过来。'
          }
        />
      </Field>
    </GroupSection>
  );
}
