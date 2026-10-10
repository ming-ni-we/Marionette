import { Input } from '@/components/ui/input';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { NumberField, ToggleRow } from './entry-fields';
import type { WorldBookData } from '@/api/types';

/* ------------------------------------------------------ 世界书级设置 */

export function WorldBookSettings({
  data,
  onChange,
}: {
  data: WorldBookData;
  onChange: (patch: Partial<WorldBookData>) => void;
}) {
  return (
    <div>
      <GroupSection id="wb-meta" title="基本信息" defaultOpen>
        <Field label="世界书名称" htmlFor="wb-name" hint="用于在内容库里识别与检索。">
          <Input
            id="wb-name"
            value={data.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="例如：旧城区 · 未名书店周边"
          />
        </Field>
        <Field label="用途说明" htmlFor="wb-desc" optional hint="一句话说清这本文档管什么。">
          <Input
            id="wb-desc"
            value={data.description}
            onChange={(e) => onChange({ description: e.target.value })}
            placeholder="例如：书店所在的旧城区地理与人情。"
          />
        </Field>
      </GroupSection>

      <GroupSection
        id="wb-budget"
        title="扫描与预算"
        description="预算决定这一本世界书最多能往上下文里塞多少内容。塞不下的会被标记为「命中但被挤出」。"
        defaultOpen
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <NumberField
            id="wb-scan-depth"
            label="扫描最近几条消息"
            hint="只看最近这么多条消息里有没有关键词。调大更容易触发，也更费 token。"
            value={data.scan_depth}
            min={1}
            max={64}
            onChange={(scan_depth) => onChange({ scan_depth })}
          />
          <NumberField
            id="wb-budget"
            label="Token 预算"
            hint="这本世界书允许占用的上限。超出的条目会被挤出。"
            value={data.token_budget}
            min={128}
            max={32768}
            step={128}
            onChange={(token_budget) => onChange({ token_budget })}
          />
        </div>

        <ToggleRow
          title="递归扫描"
          hint="新命中的条目内容再拿去做一次关键词扫描，可以形成链式触发。有深度上限，不会成环。"
          checked={data.recursive_scanning}
          onCheckedChange={(v) => onChange({ recursive_scanning: v })}
          label="启用递归扫描"
        />

        {data.recursive_scanning ? (
          <NumberField
            id="wb-recursion-depth"
            label="最大递归深度"
            hint="硬上限 3，防止链式触发无限展开。"
            value={data.max_recursion_depth}
            min={1}
            max={3}
            onChange={(max_recursion_depth) => onChange({ max_recursion_depth })}
          />
        ) : null}
      </GroupSection>
    </div>
  );
}
