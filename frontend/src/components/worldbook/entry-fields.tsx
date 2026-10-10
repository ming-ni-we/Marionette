import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Field } from '@/components/common/field';
import type { WorldBookEntry, WorldBookPosition } from '@/api/types';

export const POSITION_LABEL: Record<WorldBookPosition, string> = {
  before_char: '角色定义之前',
  after_char: '角色定义之后',
  before_example: '示例对话之前',
  after_example: '示例对话之后',
  at_depth: '按深度插进历史里',
};

export const ROLE_LABEL: Record<WorldBookEntry['role'], string> = {
  system: '旁白设定',
  user: '我的立场',
  assistant: '角色的立场',
};

/** 数字输入行（token 预算、优先级、深度等，统一等宽 + 表格数字）。 */
export function NumberField({
  id,
  label,
  hint,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <Field label={label} htmlFor={id} hint={hint}>
      <Input
        id={id}
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="font-mono tabular-nums"
      />
    </Field>
  );
}

/** 设定型开关行：标题 + 说明 + 右侧开关（世界书条目/设置里反复出现的形态）。 */
export function ToggleRow({
  title,
  hint,
  checked,
  onCheckedChange,
  label,
}: {
  title: string;
  hint: string;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-warm px-3 py-2.5">
      <div>
        <div className="text-base text-fg">{title}</div>
        <p className="mt-0.5 text-xs leading-relaxed text-muted">{hint}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} label={label} />
    </div>
  );
}
