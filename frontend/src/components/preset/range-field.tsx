import { Field } from '@/components/common/field';
import { Input } from '@/components/ui/input';

/** 滑杆 + 数值输入：参数可推导、可精确输入（配 hint 说明「这个值变大会怎样」） */
export function RangeField({
  id,
  label,
  hint,
  value,
  min,
  max,
  step,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <Field label={label} htmlFor={id} hint={hint} accessory={<span className="tech-meta">{value}</span>}>
      <div className="flex items-center gap-3">
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label={label}
          className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-surface-sunken accent-[var(--color-accent)]"
        />
        <Input
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label={`${label} 数值`}
          className="w-20 font-mono tabular-nums"
        />
      </div>
    </Field>
  );
}
