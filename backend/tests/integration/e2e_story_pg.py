"""真实端到端（真 Postgres 18 + pgvector）：跑一轮剧情，逐条比对前端契约。"""
import asyncio
import os
import sys

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/marionette"
os.environ.setdefault("SECRET_KEY", "e2e-test-secret-key-not-for-production")
os.environ.setdefault("ACCESS_PASSWORD", "e2e-test-password")
sys.path.insert(0, "/workspace/marionette/backend")

FAIL = []
def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"   [{detail}]" if detail else ""))
    if not cond:
        FAIL.append(label)

CAST = [{"id": "c1", "name": "苏晚", "role": "主角", "voice": "话少，句子短"},
        {"id": "c2", "name": "老周", "role": "配角", "voice": "嗓门大"}]
RELS = [{"from": "c1", "to": "c2", "kind": "旧识", "tension": 0.5, "note": "看着她长大"}]

class FakeRouter:
    def __init__(self, scripts):
        self._s = list(scripts)
        self.calls = 0
    async def stream(self, messages, **kw):
        self.calls += 1
        if not self._s:
            return
        for piece in self._s.pop(0):
            yield piece

    async def complete(self, *a, **k):
        return "{}"

class FakeDirector:
    def __init__(self, d): self._d = d
    async def decide(self, **kw): return self._d

class FakeSuggester:
    async def suggest(self, **kw):
        return [{"id": "a1", "label": "把伞立到门边，先不说话", "hint": "看谁先开口", "tone": "observe"},
                {"id": "a2", "label": "问苏晚那本账是谁的", "hint": "直指她藏起来的东西", "tone": "speak"},
                {"id": "a3", "label": "帮老周把门带上", "hint": "站到某一边去", "tone": "act"}]

async def main():
    from app.core.db import SessionLocal
    from app.models.card import Card
    from app.models.preset import Preset
    from app.models.world import World
    from app.services.chat import ChatSvc
    from app.services.director import DirectorDecision
    from app.services.session import SessionSvc
    from app.services.story_state import STORY_SPEC, StoryStateSvc, is_story_session

    async with SessionLocal() as db:
        # ---- 卡 + 预设（真实模型）----
        card = Card(owner_id="local", name="苏晚", spec="rpg_card", spec_version="1.0",
                    data={"name": "苏晚", "first_mes": "雨下了三天。"}, extensions={}, tags=[])
        preset = Preset(owner_id="local", name="默认", spec="rpg_preset", spec_version="1.0",
                        data={"name": "默认", "prompt_template": {"system": "你是 {{char}}", "placeholders": {}},
                              "context_budget": {"max_context_tokens": 4096, "reserve_for_output": 512}},
                        extensions={})
        # ---- 世界（真实模型，验证 0002_worlds 迁移真实可用）----
        world = World(owner_id="local", title="E2E 旧城区", spec="rpg_world", spec_version="1.0",
                      setting={"era": "雨季", "tone": "压抑", "summary": "拆迁前三十天。",
                               "locations": ["未名书店"], "rules": ["没有超自然力量"]},
                      factions=[{"id": "f1", "name": "拆迁办", "stance": "中立", "description": "按流程办事。爱用旧事压人。"}],
                      cast=CAST, relations=RELS,
                      outline={"main_goal": "查清真相",
                               "nodes": [{"id": "n1", "title": "雨夜的第一封信",
                                          "brief": "夹墙里的信", "trigger": "翻找旧物"}],
                               "endings": ["真相揭开"]},
                      opening="雨下了三天。", extensions={}, tags=["悬疑"])
        db.add_all([card, preset, world])
        await db.flush()
        print(f"  卡/预设/世界已建 world={world.id}")

        # ---- 剧情会话（直接建行，避开 create() 的序列化开销）----
        from app.models.session import Session as SessionRow
        svc = SessionSvc(db)
        row = SessionRow(
            owner_id="local", spec=STORY_SPEC, spec_version="1.0",
            card_id=card.id, preset_id=preset.id, world_id=world.id,
            worldbook_ids=[], user_persona={"name": "你", "description": "刚进店的人"},
            status="active",
            state_machine={"current": "idle", "turn": 0, "version": 0, "last_error": None},
            scene={"location": "", "time": "", "mood": "", "summary": "", "bg_asset_id": None},
            memory={"rolling_summary": "", "summary_upto_message_id": None, "facts": []},
            triggered_entries={}, extensions={},
        )
        db.add(row)
        await db.flush()
        sid = str(row.id)
        state = StoryStateSvc(db)
        state.bind_world(row, world_id=str(world.id), cast=CAST, relations=RELS)
        state.apply_scene_update(row, {"location": "未名书店", "time": "傍晚", "mood": "压抑",
                                       "beat": "第一拍", "present": ["c1", "c2"]})
        await db.flush()
        print(f"  剧情会话已建 {sid}  spec={row.spec}")

        check("会话 spec = story_session", row.spec == "story_session", row.spec)
        check("会话 world_id 已写入", str(row.world_id) == str(world.id))
        check("is_story_session 判定为真", is_story_session(row))

        # ---- 驱动一轮真实 stream_reply ----
        chat = ChatSvc(db)
        router = FakeRouter([["你来晚了。"], ["我早就来了。"]])
        chat._router = router
        chat._director = FakeDirector(DirectorDecision(
            speakers=[{"id": "c1", "name": "苏晚", "intent": "试探", "direction": "话少"},
                      {"id": "c2", "name": "老周", "intent": "施压", "direction": "嗓门大"}],
            narration="雨下了三天，墙皮泡得发胀。",
            scene_patch={"mood": "压抑"}, node_triggered={"id": "n1", "title": "雨夜的第一封信", "brief": "夹墙里的信"},
            relation_updates=[], flags={"公告已贴": True},
            reason="先摆最对立的两人，让矛盾自己浮现。", degraded=False,
        ))
        chat._suggester = FakeSuggester()

        events = []
        async for name, payload in chat.stream_reply(sid, input_text="我推门进去，把伞立在门边。"):
            events.append((name, payload))
        names = [n for n, _ in events]
        print("\n  真实事件序列:")
        print("   ", " → ".join(names), "\n")

        check("world_info 是第一个事件", names[0] == "world_info", names[0])
        check("director 在 start 之前", names.index("director") < names.index("start"))
        st = [p for n, p in events if n == "start"][0]
        check("start.message_id 为空串（剧情模式放宽）", st["message_id"] == "", repr(st["message_id"]))
        check("含 speaker_switch", "speaker_switch" in names)
        check("含 node", "node" in names)
        check("含 actions", "actions" in names)
        check("actions 在 done 之前", names.index("actions") < names.index("done"))
        check("done 是最后一个事件", names[-1] == "done")

        deltas = [(p["text"], p.get("speaker_id")) for n, p in events if n == "delta"]
        print(f"\n       delta speaker_id 序列: {[s for _, s in deltas]}")
        check("每个 delta 都带 speaker_id（前端据此落点）", all(s is not None for _, s in deltas))

        sw = [p for n, p in events if n == "speaker_switch"]
        narr = [s for s in sw if s.get("is_narration")]
        role = [s for s in sw if not s.get("is_narration")]
        check("旁白 speaker_switch 恰好 1 条", len(narr) == 1, f"实际 {len(narr)}")
        check("旁白 switch 带 message_id（前端据此 upsert）", bool(narr and narr[0].get("message_id")))
        check("角色 switch 只有 1 条 —— 首个说话者后端刻意不发", len(role) == 1,
              f"实际 {len(role)}: {[s.get('speaker_id') for s in role]}")
        check("角色 switch 指向第 2 个说话者 c2", bool(role) and role[0].get("speaker_id") == "c2")

        dir_payload = [p for n, p in events if n == "director"][0]
        check("director 带 reason（透明性面板用）", bool(dir_payload.get("reason")))
        check("director.degraded 字段存在且为 False", dir_payload.get("degraded") is False)
        acts = [p for n, p in events if n == "actions"][0]["actions"]
        check("actions 含 3 条建议且带 tone", len(acts) == 3 and all("tone" in a for a in acts))

        # ---- 落库校验 ----
        fresh = await svc.get_row(sid)
        msgs = await svc.list_messages(fresh.id)
        replies = [m for m in msgs if m.role == "assistant" and (m.meta or {}).get("beat_role") == "reply"]
        narra = [m for m in msgs if m.role == "assistant" and (m.meta or {}).get("is_narration")]
        print()
        check("reply 消息数 = 说话者数 = 2（N 说话者 = N 消息）", len(replies) == 2, f"实际 {len(replies)}")
        check("旁白消息 = 1", len(narra) == 1, f"实际 {len(narra)}")
        check("reply speaker_id 顺序 = c1,c2",
              [m.meta["speaker_id"] for m in replies] == ["c1", "c2"],
              str([m.meta.get("speaker_id") for m in replies]))
        check("reply 正文各自独立、未串行",
              [m.content for m in replies] == ["你来晚了。", "我早就来了。"],
              str([m.content for m in replies]))
        check("旁白正文未被角色台词污染",
              "墙皮泡得发胀" in narra[0].content and "你来晚了" not in narra[0].content,
              repr(narra[0].content))
        check("无残留 streaming", all(m.status != "streaming" for m in msgs))

        sm = fresh.state_machine or {}
        check("状态机回 idle", sm.get("current") == "idle", str(sm.get("current")))
        check("轮次已推进", int(sm.get("turn", 0)) >= 1, str(sm.get("turn")))

        # ---- GET /story 快照 ----
        story = state.get_story(fresh)
        scene = state.get_scene_story(fresh)
        print()
        check("story.node_id = n1", story.get("node_id") == "n1", str(story.get("node_id")))
        check("story.flags 已写入", (story.get("flags") or {}).get("公告已贴") is True)
        check("scene.mood 已更新", scene.get("mood") == "压抑", str(scene.get("mood")))

        print("\n" + "=" * 72)
        if FAIL:
            print(f"[结论] FAIL —— {len(FAIL)} 项未通过")
            for name in FAIL:
                print("   -", name)
            return 1
        print("[结论] PASS —— 真实 Postgres 上剧情链路与前端契约逐条一致")
        return 0

sys.exit(asyncio.run(main()))
