import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Field } from '@/components/common/field';
import { GroupSection } from '@/components/common/group-section';
import { EmptyState } from '@/components/common/empty-state';
import { Trash2, CirclePlus, UsersRound, Copy } from '@/components/icons';
import { StringListField } from './string-list-field';
import { nextEntityId, type WorldCastMember } from '@/api/types';

/** 角色定位（供导演分配戏份时的语气参考）。 */
const ROLE_PRESETS = ['主角', '配角', '反派', '路人'] as const;

/**
 * 角色群编辑器。
 *
 * `id` 是整个剧情引擎的**主键**：每条消息的 `meta.speaker_id`、关系图的两端、
 * `scene.present` 都引用它。因此这里做了三件事防止它被玩坏：
 *   1. 新建时由 `nextEntityId` 分配 `c1`/`c2`…（在已有集合里找空位，不复用）
 *   2. `id` 单独一行只读展示，避免用户手改后与关系图脱钩
 *   3. 删除角色时同步清理引用它的关系边（由上层 `pruneRelations` 负责）
 */
export function WorldCastPanel({
  cast,
  onChange,
  onRemove,
}: {
  cast: WorldCastMember[];
  onChange: (index: number, patch: Partial<WorldCastMember>) => void;
  onRemove: (index: number) => void;
}) {
  const add = () => {
    const id = nextEntityId('c', cast);
    onChange(cast.length, { id, name: '', role: '配角', voice: '', goals: [], description: '' });
  };

  return (
    <GroupSection
      id="world-cast"
      title="角色群"
      description="导演只能在「这里列出的角色」里挑人出场。没列进来的角色不存在——这是控制故事边界最有效的一招。"
      summary={cast.length > 0 ? `${cast.length} 人` : undefined}
      defaultOpen
    >
      {cast.length === 0 ? (
        <EmptyState
          size="compact"
          icon={UsersRound}
          title="还没有角色"
          description="至少加一个角色，剧情才有人可以说话。你也可以只加一个，先跑起来再补。"
          actions={
            <Button variant="secondary" onClick={add}>
              <CirclePlus className="size-4" aria-hidden="true" />
              添加第一个角色
            </Button>
          }
        />
      ) : (
        <ul className="space-y-4">
          {cast.map((member, i) => (
            <li key={member.id || `cast-${i}`} className="rounded-md border border-border bg-surface p-3">
              <div className="mb-3 flex items-center gap-2">
                <Badge variant="neutral" className="font-mono">
                  {member.id || '（无 id）'}
                </Badge>
                <span className="text-sm text-meta">
                  {member.name || '未命名'} · 第 {i + 1} / {cast.length}
                </span>
                <div className="ml-auto flex items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      // 复制成新角色：换新 id，名字加后缀，避免与关系图撞号
                      const newId = nextEntityId('c', [...cast, { id: '' }]);
                      onChange(cast.length, {
                        ...member,
                        id: newId,
                        name: `${member.name || '未命名'}（副本）`,
                      });
                    }}
                  >
                    <Copy className="size-4" aria-hidden="true" />
                    复制
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-danger"
                    onClick={() => onRemove(i)}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                    删除
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="名字" htmlFor={`cast-name-${i}`}>
                    <Input
                      id={`cast-name-${i}`}
                      value={member.name ?? ''}
                      onChange={(e) => onChange(i, { name: e.target.value })}
                      placeholder="例如：苏晚"
                    />
                  </Field>
                  <Field
                    label="定位"
                    htmlFor={`cast-role-${i}`}
                    hint="影响导演分配戏份的权重，不是硬限制。"
                  >
                    <Input
                      id={`cast-role-${i}`}
                      list={`cast-role-presets-${i}`}
                      value={member.role ?? ''}
                      onChange={(e) => onChange(i, { role: e.target.value })}
                      placeholder="主角 / 配角 / 反派 / 路人"
                    />
                    <datalist id={`cast-role-presets-${i}`}>
                      {ROLE_PRESETS.map((r) => (
                        <option key={r} value={r} />
                      ))}
                    </datalist>
                  </Field>
                </div>

                <Field
                  label="说话风格"
                  htmlFor={`cast-voice-${i}`}
                  hint="直接写给导演看的台词指导。例如：短句、爱用反问、从不解释自己。"
                >
                  <Input
                    id={`cast-voice-${i}`}
                    value={member.voice ?? ''}
                    onChange={(e) => onChange(i, { voice: e.target.value })}
                    placeholder="例如：话少，句子短，习惯用沉默逼对方先开口"
                  />
                </Field>

                <Field
                  label="人设简介"
                  htmlFor={`cast-desc-${i}`}
                  optional
                  hint="身份、处境、与玩家角色的既有关系。"
                >
                  <Textarea
                    id={`cast-desc-${i}`}
                    rows={3}
                    value={member.description ?? ''}
                    onChange={(e) => onChange(i, { description: e.target.value })}
                    placeholder="例如：书店的实际掌柜，替失踪的父亲守着这间店。"
                  />
                </Field>

                <StringListField
                  id={`cast-goals-${i}`}
                  label="角色目标"
                  hint="他想要什么。有目标的角色会主动制造冲突，故事才不靠玩家推。"
                  placeholder="例如：在拆迁前找到父亲留下的账本"
                  values={member.goals ?? []}
                  onChange={(goals) => onChange(i, { goals })}
                  addLabel="添加目标"
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {cast.length > 0 ? (
        <Button type="button" variant="secondary" size="sm" onClick={add}>
          <CirclePlus className="size-4" aria-hidden="true" />
          添加角色
        </Button>
      ) : null}
    </GroupSection>
  );
}
