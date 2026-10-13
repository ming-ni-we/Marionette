import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { EmptyState } from '@/components/common/empty-state';
import { Trash2, CirclePlus, ListTree } from '@/components/icons';
import { StringListField } from './string-list-field';
import { nextEntityId, type WorldOutline, type WorldOutlineNode } from '@/api/types';

/**
 * 剧情大纲编辑器。
 *
 * 节点不是「任务清单」而是**导演的触发点**：`trigger` 用自然语言写给导演看
 * （「玩家提到拆迁公告时」），由导演在每轮裁决里自行判断是否满足。
 * 触发后后端会发 `node` 事件，前端弹横幅。
 */
export function WorldOutlinePanel({
  outline,
  onChange,
}: {
  outline: WorldOutline;
  onChange: (patch: Partial<WorldOutline>) => void;
}) {
  const nodes = outline.nodes ?? [];

  const setNode = (i: number, patch: Partial<WorldOutlineNode>) =>
    onChange({ nodes: nodes.map((n, k) => (k === i ? { ...n, ...patch } : n)) });

  const addNode = () => {
    const id = nextEntityId('n', nodes);
    onChange({ nodes: [...nodes, { id, title: '', brief: '', trigger: '' }] });
  };

  return (
    <div>
      <GroupSection
        id="world-goal"
        title="主线目标"
        description="所有人都在往这个方向走。写清楚它，故事就不会散成一堆闲聊。"
        defaultOpen
      >
        <Field
          label="主线目标"
          htmlFor="world-main-goal"
          hint="一句话说清「玩家最终要达成/搞明白什么」。"
        >
          <Textarea
            id="world-main-goal"
            rows={3}
            value={outline.main_goal ?? ''}
            onChange={(e) => onChange({ main_goal: e.target.value })}
            placeholder="例如：在拆迁动工前查清父亲失踪那晚发生了什么。"
          />
        </Field>
      </GroupSection>

      <GroupSection
        id="world-nodes"
        title="关键节点"
        description="导演会在每轮判断「触发条件」是否满足，满足就触发并把故事推向下一幕。不写也不影响推进，只是少了几个明确的路标。"
        summary={nodes.length > 0 ? `${nodes.length} 个` : undefined}
        defaultOpen
      >
        {nodes.length === 0 ? (
          <EmptyState
            size="compact"
            icon={ListTree}
            title="还没有关键节点"
            description="节点是可选的。它适合放「必须发生」的转折点——比如真相揭穿的那一刻。"
            actions={
              <Button variant="secondary" onClick={addNode}>
                <CirclePlus className="size-4" aria-hidden="true" />
                添加第一个节点
              </Button>
            }
          />
        ) : (
          <ul className="space-y-4">
            {nodes.map((node, i) => (
              <li key={node.id || `node-${i}`} className="rounded-md border border-border bg-surface p-3">
                <div className="mb-3 flex items-center gap-2">
                  <Badge variant="neutral" className="font-mono">
                    {node.id || '（无 id）'}
                  </Badge>
                  <span className="text-sm text-meta">
                    {node.title || '未命名节点'} · 第 {i + 1} / {nodes.length}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="ml-auto text-danger"
                    onClick={() => onChange({ nodes: nodes.filter((_, k) => k !== i) })}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                    删除
                  </Button>
                </div>

                <div className="space-y-3">
                  <Field label="节点标题" htmlFor={`node-title-${i}`}>
                    <Input
                      id={`node-title-${i}`}
                      value={node.title ?? ''}
                      onChange={(e) => setNode(i, { title: e.target.value })}
                      placeholder="例如：账本现身"
                    />
                  </Field>

                  <Field
                    label="触发条件"
                    htmlFor={`node-trigger-${i}`}
                    hint="写给导演看的自然语言条件。写具体一点，导演才判得准。"
                  >
                    <Input
                      id={`node-trigger-${i}`}
                      value={node.trigger ?? ''}
                      onChange={(e) => setNode(i, { trigger: e.target.value })}
                      placeholder="例如：玩家与苏晚独处且提到父亲"
                    />
                  </Field>

                  <Field
                    label="节点内容"
                    htmlFor={`node-brief-${i}`}
                    optional
                    hint="触发时该发生什么。这段会出现在导演的当前上下文里。"
                  >
                    <Textarea
                      id={`node-brief-${i}`}
                      rows={3}
                      value={node.brief ?? ''}
                      onChange={(e) => setNode(i, { brief: e.target.value })}
                      placeholder="例如：苏晚终于拿出那本缺页的账本，但只肯让玩家看其中一页。"
                    />
                  </Field>
                </div>
              </li>
            ))}
          </ul>
        )}

        {nodes.length > 0 ? (
          <Button type="button" variant="secondary" size="sm" onClick={addNode}>
            <CirclePlus className="size-4" aria-hidden="true" />
            添加节点
          </Button>
        ) : null}
      </GroupSection>

      <GroupSection
        id="world-endings"
        title="结局倾向"
        description="不是剧本，是给导演的方向感。写几条你希望故事可能走向的终点。"
        defaultOpen={false}
      >
        <StringListField
          id="world-endings"
          label="结局倾向"
          hint="开放式描述即可。导演会朝这些方向收束，不保证命中哪一条。"
          placeholder="例如：真相被揭开，但代价是失去这间书店"
          values={outline.endings ?? []}
          onChange={(endings) => onChange({ endings })}
          addLabel="添加结局倾向"
        />
      </GroupSection>
    </div>
  );
}
