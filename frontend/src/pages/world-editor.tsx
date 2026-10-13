import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { emptyWorld, cardsApi, presetsApi, sessionsApi, worldsApi } from '@/api/client';
import type {
  WorldCastMember,
  WorldInput,
  WorldRelation,
  WorldSetting,
  WorldOutline,
} from '@/api/types';
import { toast } from '@/stores/ui';
import { WorldEditorHeader } from '@/components/world/editor-header';
import { WorldSettingPanel } from '@/components/world/setting-panel';
import { WorldCastPanel } from '@/components/world/cast-panel';
import { WorldRelationsPanel, pruneRelations } from '@/components/world/relations-panel';
import { WorldOutlinePanel } from '@/components/world/outline-panel';
import { WorldOpeningPanel } from '@/components/world/opening-panel';
import { ErrorState } from '@/components/common/empty-state';
import { OfflineBanner } from '@/components/common/offline-banner';
import { NavList, GroupSection } from '@/components/common/group-section';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Field } from '@/components/common/field';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Compass } from '@/components/icons';

/** 左侧锚点导航（分组 id 与各面板 GroupSection 的 id 一一对应）。 */
const NAV_ITEMS = [
  { id: 'world-basics', label: '基本信息', hint: '名称 · 标签' },
  { id: 'world-setting', label: '时空与基调', hint: '时代 · 氛围 · 总览' },
  { id: 'world-places-rules', label: '地点与规则', hint: '硬约束' },
  { id: 'world-cast', label: '角色群', hint: '导演的演员表' },
  { id: 'world-relations', label: '角色关系', hint: '张力与立场' },
  { id: 'world-goal', label: '主线目标', hint: '故事往哪走' },
  { id: 'world-nodes', label: '关键节点', hint: '转折触发点' },
  { id: 'world-endings', label: '结局倾向', hint: '可选' },
  { id: 'world-opening', label: '开场序幕', hint: '可选' },
];

/**
 * 世界观编辑器（新建 / 编辑）。
 *
 * 与角色卡、世界书编辑器的差异：这里是**表单驱动**而非「列表 + 详情」，
 * 因为世界观的各维度（设定/角色/关系/大纲）互相引用（关系图依赖角色群、
 * 节点依赖主线），拆成多个页面会让用户在页面间反复跳。
 *
 * 一条重要约束：**必须已保存才能开演**。因为剧情会话创建时会读取后端的
 * cast/relations 做固化（`StoryStateSvc.bind_world`），草稿状态的数据不存在于
 * 后端，硬开演只会得到一个空壳会话。所以「开演」按钮在 dirty 时禁用。
 */
export function WorldEditorPage() {
  const { worldId = '' } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const isNew = !worldId || worldId === 'new';

  const query = useQuery({
    queryKey: ['world', worldId],
    queryFn: () => worldsApi.get(worldId),
    enabled: !isNew,
    retry: false,
  });

  /**
   * 「开演」要用的卡片与预设清单。
   *
   * 剧情会话创建时后端**强制要求** `character_card_id` / `preset_id` 两个真实
   * UUID（`SessionCreateRequest`），且 `create_story_session()` 会真的去查这两行，
   * 查不到就抛 `NotFoundError`。所以「用这个世界开演」不能只传 `world_id` ——
   * 之前这里传了空串，必然被后端拒（Pydantic 422 或 400 缺少必填参数）。
   *
   * 这里拉全量清单，配合下面的 `linkedCardId` / `defaultPresetId` 自动补默认值，
   * 让「一键开演」仍然是一键。
   */
  const cardsQ = useQuery({
    queryKey: ['cards', 'world-play'],
    queryFn: () => cardsApi.list({ limit: 100 }),
    retry: false,
  });
  const presetsQ = useQuery({
    queryKey: ['presets', 'world-play'],
    queryFn: () => presetsApi.list({ limit: 100 }),
    retry: false,
  });

  const [draft, setDraft] = useState<WorldInput>(emptyWorld);
  const [dirty, setDirty] = useState(false);
  const [activeId, setActiveId] = useState('world-basics');
  const loadedRef = useRef<string | null>(null);
  const mainRef = useRef<HTMLDivElement>(null);

  // 后端数据到达 → 灌进草稿（用 loadedRef 防止用户编辑被回填覆盖）
  useEffect(() => {
    const row = query.data;
    if (row && loadedRef.current !== row.id) {
      const { id: _id, created_at: _c, updated_at: _u, ...rest } = row;
      setDraft({
        spec: rest.spec || 'rpg_world',
        spec_version: rest.spec_version || '1.0',
        title: rest.title ?? '',
        setting: { ...emptyWorld().setting, ...(rest.setting ?? {}) },
        factions: rest.factions ?? [],
        cast: rest.cast ?? [],
        relations: rest.relations ?? [],
        outline: { ...emptyWorld().outline, ...(rest.outline ?? {}) },
        opening: rest.opening ?? '',
        extensions: rest.extensions ?? {},
        tags: rest.tags ?? [],
      });
      setDirty(false);
      loadedRef.current = row.id;
    }
  }, [query.data]);

  useEffect(() => {
    if (isNew) {
      setDraft(emptyWorld());
      setDirty(false);
      loadedRef.current = 'new';
    }
  }, [isNew]);

  const patch = (p: Partial<WorldInput>) => {
    setDraft((d) => ({ ...d, ...p }));
    setDirty(true);
  };

  /* --------------------------------------------------------- 角色群操作 */

  const patchCast = (index: number, p: Partial<WorldCastMember>) => {
    setDraft((d) => {
      // index === d.cast.length 表示「追加」——CastPanel 的复制/添加走这条路径，
      // 避免它必须先构造完整对象再回传数组（那样会丢掉并发的其他编辑）。
      const cast = [...d.cast];
      if (index >= cast.length) cast.push({ id: '', name: '', ...p } as WorldCastMember);
      else cast[index] = { ...cast[index], ...p };
      return { ...d, cast };
    });
    setDirty(true);
  };

  const removeCast = (index: number) => {
    setDraft((d) => {
      const cast = d.cast.filter((_, i) => i !== index);
      // 同步清理指向已删角色的关系边，否则会留下悬空引用
      return { ...d, cast, relations: pruneRelations(d.relations, cast) };
    });
    setDirty(true);
  };

  const canSave = useMemo(() => draft.title.trim().length > 0, [draft.title]);

  /* ------------------------------------------------------------- 保存 */

  const save = useMutation({
    mutationFn: () => {
      const payload: WorldInput = { ...draft, title: draft.title.trim() };
      return isNew ? worldsApi.create(payload) : worldsApi.update(worldId, payload);
    },
    onSuccess: (world) => {
      setDirty(false);
      toast.success(isNew ? '世界已创建' : '已保存');
      void qc.invalidateQueries({ queryKey: ['worlds'] });
      void qc.invalidateQueries({ queryKey: ['world', world.id] });
      if (isNew) navigate(`/worlds/${world.id}`, { replace: true });
    },
    onError: () => toast.danger('保存失败', '后端拒绝了这次写入，请检查必填字段。'),
  });

  /**
   * 「开演」用的角色卡：优先取 cast 上显式关联的卡，其次按名字匹配，最后兜底第一张。
   *
   * 与 `new-session-dialog.tsx` 的 `linkedCardId` 同一套优先级 —— 那边是用户在
   * 对话框里显式选，这边是编辑器里的**一键开演**（无选卡界面），所以更依赖自动补：
   *   1. cast 成员上写的 `card_id`（作者指定，最权威）
   *   2. cast 成员的 `name` 与卡片 `data.name` 同名（老数据的常见形态）
   *   3. 兜底：第一张卡
   */
  const linkedCardId = useMemo(() => {
    const cards = cardsQ.data?.items ?? [];
    for (const member of draft.cast ?? []) {
      if (member.card_id) {
        const hit = cards.find((c) => c.id === member.card_id);
        if (hit) return hit.id;
      }
    }
    for (const member of draft.cast ?? []) {
      const hit = cards.find((c) => c.data.name === member.name);
      if (hit) return hit.id;
    }
    return cards[0]?.id ?? '';
  }, [cardsQ.data, draft.cast]);

  /** 开演用的预设：一键开演没有选预设的界面，取第一份可用预设。 */
  const defaultPresetId = presetsQ.data?.items?.[0]?.id ?? '';

  /** 两个必填项都齐了才允许开演 —— 否则让按钮禁用并说明原因，别再让用户吃一次 400。 */
  const canPlay = !dirty && !isNew && Boolean(linkedCardId) && Boolean(defaultPresetId);

  const playBlockReason = dirty
    ? '先保存改动再开演。'
    : isNew
      ? '先保存这个世界才能开演。'
      : !linkedCardId
        ? '内容库里还没有角色卡。先建一张，或在角色群里关联已有卡。'
        : !defaultPresetId
          ? '还没有可用的预设。请先在「预设」里建一份。'
          : '';

  /**
   * 开演：先建会话再跳转。
   *
   * 剧情会话需要 `character_card_id` / `preset_id`——即使多角色模式下主角由
   * 世界观的角色群定义，后端仍要求这两个字段（沿用 1v1 的表约束），且会真的
   * 查这两行。所以这里必须传**真实 id**，空串会被 422/400 直接拒。
   */
  const play = useMutation({
    mutationFn: () =>
      sessionsApi.create({
        character_card_id: linkedCardId,
        preset_id: defaultPresetId,
        world_id: worldId,
      }),
    onSuccess: (session) => navigate(`/stories/${session.id}`),
    onError: () =>
      toast.danger(
        '无法开演',
        '创建剧情会话失败。请确认后端已配置模型，并且这个世界至少有一个角色。',
      ),
  });

  const scrollTo = (id: string) => {
    setActiveId(id);
    // 分组是一个个 GroupSection，用 id 直接命中它的内容容器
    const el = document.getElementById(`${id}-content`) ?? document.getElementById(id);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (!isNew && query.isError) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-10">
        <ErrorState
          description={`没找到这个世界观（id: ${worldId}）。它可能已被删除，或当前后端实例换了数据库。`}
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link to="/worlds">回到剧情世界</Link>
              </Button>
              <Button variant="ghost" asChild>
                <Link to="/worlds/new">新建一个世界</Link>
              </Button>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <WorldEditorHeader
        title={draft.title}
        isNew={isNew}
        demo={false}
        dirty={dirty}
        castCount={draft.cast.length}
        relationCount={draft.relations.length}
        nodeCount={draft.outline?.nodes?.length ?? 0}
        saving={save.isPending}
        canSave={canSave}
        onSave={() => save.mutate()}
        onPlay={() => play.mutate()}
        playDisabled={!canPlay}
        playBlockReason={playBlockReason}
      />

      {query.isError ? (
        <OfflineBanner>这个世界观尚未保存到后端，修改不会生效。</OfflineBanner>
      ) : null}

      <div className="grid flex-1 grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* 左：锚点导航（世界观的字段分组较多，必须给出全局定位） */}
        <aside className="hidden border-r border-border p-4 lg:block">
          <div className="sticky top-20">
            <span className="mb-2 block label-caps">世界结构</span>
            <NavList items={NAV_ITEMS} activeId={activeId} onSelect={scrollTo} />
            <p className="mt-4 border-t border-border-soft pt-3 text-xs leading-relaxed text-meta">
              世界各维度互相引用：关系图依赖角色群，节点依赖主线。改完角色记得回来看一眼关系。
            </p>
          </div>
        </aside>

        {/* 右：表单主体 */}
        <ScrollArea className="min-w-0">
          <div ref={mainRef} className="mx-auto max-w-3xl px-6 py-4">
            <GroupSection
              id="world-basics"
              title="基本信息"
              description="名称用于在列表里识别与检索。"
              defaultOpen
            >
              <Field
                label="世界名称"
                htmlFor="world-title"
                error={draft.title.trim() ? undefined : '名称不能为空，否则无法保存。'}
              >
                <Input
                  id="world-title"
                  value={draft.title}
                  onChange={(e) => patch({ title: e.target.value })}
                  placeholder="例如：旧城区 · 拆迁前三十天"
                />
              </Field>

              <Field
                label="标签"
                htmlFor="world-tags"
                optional
                hint="用逗号分隔。例如：悬疑, 现代, 群像"
              >
                <Input
                  id="world-tags"
                  value={draft.tags.join(', ')}
                  onChange={(e) =>
                    patch({
                      tags: e.target.value
                        .split(',')
                        .map((t) => t.trim())
                        .filter(Boolean),
                    })
                  }
                  placeholder="悬疑, 现代, 群像"
                />
              </Field>
            </GroupSection>

            <WorldSettingPanel
              setting={draft.setting}
              onChange={(p: Partial<WorldSetting>) => patch({ setting: { ...draft.setting, ...p } })}
            />

            <WorldCastPanel cast={draft.cast} onChange={patchCast} onRemove={removeCast} />

            <WorldRelationsPanel
              relations={draft.relations}
              cast={draft.cast}
              onChange={(relations: WorldRelation[]) => patch({ relations })}
            />

            <WorldOutlinePanel
              outline={draft.outline}
              onChange={(p: Partial<WorldOutline>) => patch({ outline: { ...draft.outline, ...p } })}
            />

            <WorldOpeningPanel opening={draft.opening} onChange={(opening) => patch({ opening })} />

            {/* 底部再放一次保存：长表单滚到底后不必再回顶栏 */}
            <div className="flex items-center justify-between gap-3 border-t border-border-soft py-5">
              <span className="text-sm text-meta">
                {canSave ? '写完了就保存。' : '先给世界起个名字。'}
              </span>
              <div className="flex items-center gap-2">
                {!isNew && !dirty ? (
                  <Button
                    variant="secondary"
                    onClick={() => play.mutate()}
                    loading={play.isPending}
                    disabled={!canPlay}
                    title={canPlay ? undefined : playBlockReason}
                  >
                    <Compass className="size-4" aria-hidden="true" />
                    用这个世界开演
                  </Button>
                ) : null}
                <Button
                  variant="primary"
                  onClick={() => save.mutate()}
                  loading={save.isPending}
                  disabled={!canSave}
                >
                  保存
                </Button>
              </div>
            </div>
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
