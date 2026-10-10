import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { TagInput } from '@/components/common/tag-input';
import { estimateTokens } from '@/components/cards/card-preview';
import { NumberField, ROLE_LABEL, POSITION_LABEL, ToggleRow } from './entry-fields';
import type { WorldBookEntry, WorldBookPosition } from '@/api/types';

/* ------------------------------------------------------------ 条目编辑器 */

export function EntryEditor({
  entry,
  onChange,
}: {
  entry: WorldBookEntry;
  onChange: (patch: Partial<WorldBookEntry>) => void;
}) {
  return (
    <div>
      <GroupSection
        id="wb-trigger"
        title="触发条件"
        description="不填关键词也可以——勾选「常驻」就让这条每轮都生效。"
        defaultOpen
      >
        <Field label="备注名" htmlFor="entry-comment" hint="只给你自己看，用于在左侧列表里认出这条。">
          <Input
            id="entry-comment"
            value={entry.comment}
            onChange={(e) => onChange({ comment: e.target.value })}
            placeholder="例如：物件 · 怀表"
          />
        </Field>

        <ToggleRow
          title="常驻"
          hint="开启后不需要关键词，每次组装都会注入。适合地点基调、世界规则这类底层设定。"
          checked={entry.constant}
          onCheckedChange={(v) => onChange({ constant: v })}
          label="常驻条目"
        />

        {!entry.constant ? (
          <>
            <Field
              label="触发关键词"
              htmlFor="entry-keys"
              hint="最近对话里出现其中任意一个词，这条就会被触发。中文支持子串匹配。"
            >
              <TagInput
                tags={entry.keys}
                onChange={(keys) => onChange({ keys })}
                placeholder="输入关键词后回车，例如：怀表"
                ariaLabel="触发关键词"
                tone="accent"
              />
            </Field>

            <ToggleRow
              title="需要次级关键词同时命中"
              hint="用来避免误触发。例如「拆迁」只有在同时提到「旧城区」时才生效。"
              checked={entry.selective}
              onCheckedChange={(v) => onChange({ selective: v })}
              label="启用次级关键词"
            />

            {entry.selective ? (
              <Field label="次级关键词" htmlFor="entry-secondary" hint="必须同时出现，才认为这条命中。">
                <TagInput
                  tags={entry.secondary_keys}
                  onChange={(secondary_keys) => onChange({ secondary_keys })}
                  placeholder="例如：旧城区"
                  ariaLabel="次级关键词"
                />
              </Field>
            ) : null}
          </>
        ) : null}
      </GroupSection>

      <GroupSection
        id="wb-content"
        title="注入内容"
        description="命中的时候，这段文字会原样进入模型的上下文。"
        defaultOpen
      >
        <Field
          label="内容"
          htmlFor="entry-content"
          hint="建议用【标签】开头分段，模型更容易分清这是设定而不是台词。"
          accessory={<span className="tech-meta">约 {estimateTokens(entry.content)} tok</span>}
        >
          <Textarea
            id="entry-content"
            value={entry.content}
            onChange={(e) => onChange({ content: e.target.value })}
            placeholder="【物件】黄铜怀表：表壳有细密划痕，停在三点十七分……"
            className="min-h-32"
          />
        </Field>
      </GroupSection>

      <GroupSection
        id="wb-order"
        title="插入位置与优先级"
        description="决定这条内容插在上下文的哪一段，以及在预算不够时谁先被丢。"
        defaultOpen
      >
        <Field
          label="插入位置"
          htmlFor="entry-position"
          hint="通常「角色定义之后」就够用；需要贴着当前剧情时才用「按深度插进历史里」。"
        >
          <Select
            value={entry.position}
            onValueChange={(v) => onChange({ position: v as WorldBookPosition })}
          >
            <SelectTrigger id="entry-position">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(POSITION_LABEL) as WorldBookPosition[]).map((p) => (
                <SelectItem key={p} value={p}>
                  {POSITION_LABEL[p]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        {entry.position === 'at_depth' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              id="entry-depth"
              label="倒数第几条"
              hint="1 = 紧贴最新一条消息之前。"
              value={entry.depth}
              min={1}
              max={64}
              onChange={(depth) => onChange({ depth })}
            />
            <Field
              label="作为谁的发言"
              htmlFor="entry-role"
              hint="决定模型把这段当成旁白还是某方的话。"
            >
              <Select
                value={entry.role}
                onValueChange={(v) => onChange({ role: v as WorldBookEntry['role'] })}
              >
                <SelectTrigger id="entry-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(ROLE_LABEL) as WorldBookEntry['role'][]).map((r) => (
                    <SelectItem key={r} value={r}>
                      {ROLE_LABEL[r]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <NumberField
            id="entry-order"
            label="插入顺序"
            hint="数字小的排前面。同一位置有多条时用它决定先后。"
            value={entry.insertion_order}
            min={0}
            max={9999}
            onChange={(insertion_order) => onChange({ insertion_order })}
          />
          <NumberField
            id="entry-priority"
            label="优先级"
            hint="预算不够时会先丢掉优先级低的条目。数字越大越不会被丢。"
            value={entry.priority}
            min={0}
            max={1000}
            onChange={(priority) => onChange({ priority })}
          />
        </div>
      </GroupSection>

      <GroupSection
        id="wb-advanced"
        title="高级匹配"
        description="只有关键词匹配不听话（误触发、漏触发）时才需要动这里。"
        defaultOpen={false}
        summary={<span className="tech-meta">通常无需修改</span>}
      >
        <ToggleRow
          title="用正则匹配"
          hint="关键词写成正则表达式。编译失败会自动退回字面匹配，不会让会话中断。"
          checked={entry.use_regex}
          onCheckedChange={(v) => onChange({ use_regex: v })}
          label="用正则匹配关键词"
        />

        {entry.use_regex ? (
          <Field label="正则标志" htmlFor="entry-flags" hint="i = 忽略大小写，m = 多行。">
            <Input
              id="entry-flags"
              value={entry.regex_flags}
              onChange={(e) => onChange({ regex_flags: e.target.value })}
              className="font-mono"
              placeholder="i"
            />
          </Field>
        ) : null}

        <ToggleRow
          title="区分大小写"
          hint="中文设定一般不需要开。"
          checked={entry.case_sensitive}
          onCheckedChange={(v) => onChange({ case_sensitive: v })}
          label="区分大小写"
        />

        <ToggleRow
          title="整词匹配"
          hint="开启后只在词边界匹配，减少「关键词是另一个词的一部分」造成的误触发。"
          checked={entry.match_whole_words}
          onCheckedChange={(v) => onChange({ match_whole_words: v })}
          label="整词匹配"
        />
      </GroupSection>
    </div>
  );
}
