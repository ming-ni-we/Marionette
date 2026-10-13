import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Field } from '@/components/common/field';
import { Trash2, CirclePlus } from '@/components/icons';

/**
 * 字符串列表编辑器（核心地点 / 世界规则 / 结局倾向都用它）。
 *
 * 为什么不做成标签输入：这些是**有序、可长**的自然语言短语（"旧城区的雨夜"），
 * 逐行编辑比逗号分隔更好改、更好读，也与「一行一条规则」的模型预期一致。
 */
export function StringListField({
  id,
  label,
  hint,
  placeholder,
  values,
  onChange,
  addLabel = '添加一行',
}: {
  id: string;
  label: string;
  hint?: string;
  placeholder?: string;
  values: string[];
  onChange: (next: string[]) => void;
  addLabel?: string;
}) {
  const setAt = (i: number, v: string) => onChange(values.map((x, k) => (k === i ? v : x)));
  const removeAt = (i: number) => onChange(values.filter((_, k) => k !== i));

  return (
    <Field label={label} htmlFor={id} optional hint={hint}>
      <div className="space-y-2">
        {values.length === 0 ? (
          <p className="rounded-md border border-dashed border-border-soft px-3 py-2.5 text-sm text-meta">
            还没有内容。留空也可以——只是导演手里少了一张牌。
          </p>
        ) : (
          <ul className="space-y-2">
            {values.map((value, i) => (
              // 行没有稳定 id（用户可任意增删重排），用下标 + 长度兜底；
              // 这里不涉及受控输入焦点丢失问题（删除时才重排）。
              <li key={`${id}-${i}`} className="flex items-center gap-2">
                <Input
                  value={value}
                  placeholder={placeholder}
                  aria-label={`${label} 第 ${i + 1} 条`}
                  onChange={(e) => setAt(i, e.target.value)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="shrink-0 text-danger"
                  aria-label={`删除第 ${i + 1} 条`}
                  onClick={() => removeAt(i)}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
        )}
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange([...values, ''])}>
          <CirclePlus className="size-4" aria-hidden="true" />
          {addLabel}
        </Button>
      </div>
    </Field>
  );
}
