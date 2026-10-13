"""上下文组装器（Context Engineering，架构 §4.6）—— 产品护城河。

按 §4.6 的骨架顺序组装最终 prompt，并用 preset.context_budget 分配 token 预算、超限裁剪。

组装顺序（模型看到的顺序）：
  [1] 系统基座      preset.prompt_template.system（占位符单遍替换）
  [2] 角色定义块    name / description / personality / scenario
  [3] 世界书 · before_char 命中条目
  [4] 长期记忆块    滚动摘要(A) + 关键事实(B)
  [5] 向量召回块    C（v1 默认关闭，占位）
  [6] 示例对话      mes_example（如预算允许）
  [7] 世界书 · before_example / after_example 命中条目
  [8] 历史消息      最近 N 轮（oldest→newest），受历史预算约束
  [9] 世界书 · at_depth 命中条目
  [10] 历史后指令   post_history_instructions

剧情模式在此之上追加三段（**仅当调用方显式传入剧情 kwargs 时出现**，
否则老 9 段组装结果逐字节不变 —— 见 S5 快照测试）：
  [S1] story_state   幕/拍点/flag/待触发节点 + 在场角色（永不裁剪，硬截断 400 tok）
  [S2] relations     与「本轮说话者」相关的关系子图（按 tension 降序截断）
  [S3] cast_roster   在场角色 id/name/voice 一行摘要
三段均插入在系统消息内、`memory` 之后 —— 位置紧跟角色定义与记忆，
让模型先建立「我是谁」，再知道「世界现在什么样」。

铁律：
  - 世界书三态判定**复用** services/world_info.py 的 WorldInfoEngine，不另写一套。
  - 占位符单遍替换；未知占位符**原样保留**并记 warnings。
  - 组装结果全量可复现（prompt 全文 + 各段 token + 世界书 trace + 预算占用）。
  - 永不裁剪：当前用户消息、系统基座、角色核心定义、post_history_instructions。

本模块不触碰数据库，纯函数式：入参为已取好的 dict，便于确定性测试与黄金快照。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.adapters.base import ChatMessage
from app.services.tokens import estimate_tokens
from app.services.world_info import WorldInfoEngine

# 占位符 {{key}}
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")

# 三段预算在 §4.6 之外，历史最低保留的「软下限」比例（占比不足时按此兜底）
_DEFAULT_BUDGET = {
    "max_context_tokens": 8192,
    "reserve_for_output": 1024,
    "character_pct": 15,
    "world_info_pct": 25,
    "memory_pct": 15,
    "vector_recall_pct": 5,
    "history_pct": 35,
}

# 剧情模式三段（可选，缺省不占预算 —— 老 1v1 路径零影响）
#   story_pct    幕/拍点/flag/待触发节点 + 在场角色（硬截断，永不裁剪）
#   relations_pct 与说话者相关的关系子图
#   cast_pct      在场角色一行摘要
_STORY_BUDGET = {
    "story_pct": 8,
    "relations_pct": 6,
    "cast_pct": 5,
}

#: story_state 段即便超预算也不裁剪，但硬截断到此上限（防导演写飞）
_STORY_HARD_CAP_TOKENS = 400


@dataclass
class AssembledContext:
    """组装结果（对应 ContextSnapshot schema）。"""

    messages: list[ChatMessage] = field(default_factory=list)
    prompt_text: str = ""
    segments: list[dict[str, Any]] = field(default_factory=list)
    world_info_trace: list[dict[str, Any]] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    estimated_prompt_tokens: int = 0
    warnings: list[str] = field(default_factory=list)
    triggered_entry_ids: list[str] = field(default_factory=list)
    assembled_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "prompt_text": self.prompt_text,
            "segments": self.segments,
            "world_info_trace": self.world_info_trace,
            "budget": self.budget,
            "estimated_prompt_tokens": self.estimated_prompt_tokens,
            "actual_prompt_tokens": None,
            # 落库为 JSONB，datetime 需先转 ISO 字符串（json.dumps 不接受 datetime）
            "assembled_at": self.assembled_at.isoformat(),
        }


class ContextAssembler:
    """把角色卡 / 世界书命中 / 记忆 / 历史装配成最终 prompt。"""

    def __init__(self, world_engine: WorldInfoEngine | None = None) -> None:
        self._world = world_engine or WorldInfoEngine()

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #
    def assemble(
        self,
        *,
        card: dict[str, Any],
        preset: dict[str, Any],
        user_persona: dict[str, Any],
        history: list[dict[str, Any]],
        worldbooks: list[dict[str, Any]] | None = None,
        memory: dict[str, Any] | None = None,
        scan_text: str | None = None,
        speaking_as: dict[str, Any] | None = None,
        story_block: str = "",
        relations_block: str = "",
        node_block: str = "",
        cast_roster: list[dict[str, Any]] | None = None,
    ) -> AssembledContext:
        """组装最终 prompt。

        参数均为普通 dict（已从 ORM 反序列化）：
          - card：CardData（name/description/personality/scenario/first_mes/mes_example/...）
          - preset：PresetData（prompt_template/sampling/context_budget/...）
          - user_persona：{name, description}
          - history：[{role, content, ...}]，oldest→newest
          - worldbooks：[WorldBookData]，含 entries / token_budget
          - memory：{rolling_summary, facts[], summary_upto_message_id}
          - scan_text：世界书扫描文本；缺省用最近历史 + 用户输入拼接

        剧情模式可选参数（**全部缺省即 1v1，老调用零影响**）：
          - speaking_as：本轮说话者 {id,name,voice,goals}，用于裁剪关系子图
          - story_block：已渲染的剧情状态块（幕后/拍点/flag/待触发节点）
          - relations_block：已渲染的关系图块（调用方可用 speaking_as 预裁剪）
          - node_block：已渲染的待触发节点块（并入 story_state 段渲染）
          - cast_roster：在场角色列表，用于生成一行摘要段
        """
        warnings: list[str] = []
        preset_data = preset or {}
        budget_cfg = {
            **_DEFAULT_BUDGET,
            **_STORY_BUDGET,
            **(preset_data.get("context_budget") or {}),
        }

        # 占位符取值表（供模板替换）
        template = (preset_data.get("prompt_template") or {}).get("system", "")
        custom_placeholders = (preset_data.get("prompt_template") or {}).get("placeholders") or {}
        placeholders: dict[str, str] = {
            "char": str(card.get("name") or ""),
            "user": str(user_persona.get("name") or "Player"),
            "persona": str(user_persona.get("description") or ""),
            "description": str(card.get("description") or ""),
            "personality": str(card.get("personality") or ""),
            "scenario": str(card.get("scenario") or ""),
            "original": str(card.get("system_prompt") or ""),
        }
        placeholders.update({str(k): str(v) for k, v in custom_placeholders.items()})

        # ---- 世界书触发（三态判定复用 WorldInfoEngine）----
        scan = scan_text if scan_text is not None else self._default_scan_text(history, user_persona)
        decisions = self._run_world_info(worldbooks or [], scan, budget_cfg, warnings)

        world_before = self._world_block(decisions, {"before_char", "after_char"})
        world_example = self._world_block(decisions, {"before_example", "after_example"})
        world_at_depth = self._world_block(decisions, {"at_depth"})
        triggered_ids = [d["entry_id"] for d in decisions if d.get("in_budget")]

        # 世界书块回填到占位符（模板若未显式放 {{world_info}} 也保留）
        placeholders["world_info"] = world_before
        memory_block = self._memory_block(memory or {})
        placeholders["memory"] = memory_block

        # ---- [1] 系统基座 ----
        system_text = self._render(template, placeholders, warnings)

        # ---- [2] 角色定义块 ----
        character_block = self._character_block(card)

        # ---- [S1..S3] 剧情模式三段（缺省全空 → 不产生任何段）----
        story_state_block = self._story_state_block(story_block, node_block, budget_cfg)
        relations_rendered = self._relations_rendered(relations_block, speaking_as, budget_cfg)
        cast_roster_block = self._cast_roster_block(cast_roster)

        # ---- [6] 示例对话 ----
        examples_block = self._examples_block(card, placeholders)

        # ---- [10] 历史后指令 ----
        post_history = str(card.get("post_history_instructions") or "")
        instruction = str((preset_data.get("prompt_template") or {}).get("instruction") or "")

        # ---- token 预算裁剪：历史段按 budget 分配 ----
        total_budget = max(0, int(budget_cfg["max_context_tokens"]) - int(budget_cfg["reserve_for_output"]))
        fixed_tokens = (
            estimate_tokens(system_text)
            + estimate_tokens(character_block)
            + estimate_tokens(world_before)
            + estimate_tokens(memory_block)
            + estimate_tokens(story_state_block)
            + estimate_tokens(relations_rendered)
            + estimate_tokens(cast_roster_block)
            + estimate_tokens(examples_block)
            + estimate_tokens(world_example)
            + estimate_tokens(world_at_depth)
            + estimate_tokens(post_history)
            + estimate_tokens(instruction)
        )
        history_budget = max(0, total_budget - fixed_tokens)
        kept_history, dropped = self._trim_history(history, history_budget)

        # ---- 组装最终 messages（system + history + at_depth + post_history）----
        messages: list[ChatMessage] = []
        system_parts = [p for p in (system_text, character_block, world_before, memory_block,
                                    story_state_block, relations_rendered, cast_roster_block,
                                    examples_block, world_example) if p.strip()]
        if system_parts:
            messages.append(ChatMessage(role="system", content="\n\n".join(system_parts)))
        for item in kept_history:
            role = str(item.get("role") or "user")
            if role == "system":
                # 系统消息并入 system 段更稳妥，避免多 system 断言
                messages.append(ChatMessage(role="system", content=str(item.get("content") or "")))
            else:
                messages.append(ChatMessage(role=role, content=str(item.get("content") or "")))
        for depth_block in ([world_at_depth] if world_at_depth.strip() else []):
            messages.append(ChatMessage(role="system", content=depth_block))
        if post_history.strip():
            messages.append(ChatMessage(role="system", content=post_history))
        if instruction.strip():
            messages.append(ChatMessage(role="system", content=instruction))

        prompt_text = "\n".join(
            f"{m.role}: {m.content}" for m in messages
        )
        estimated = estimate_tokens(prompt_text)
        if estimated > total_budget:
            warnings.append(
                f"估算 prompt token {estimated} 仍超出可用预算 {total_budget}，"
                "已尽量裁剪历史（系统基座与角色定义永不裁剪）。"
            )

        segments = [
            {"name": "system", "token_count": estimate_tokens(system_text)},
            {"name": "character", "token_count": estimate_tokens(character_block)},
            {"name": "world_info_before", "token_count": estimate_tokens(world_before)},
            {"name": "memory", "token_count": estimate_tokens(memory_block)},
            {"name": "vector_recall", "token_count": 0},
            {"name": "examples", "token_count": estimate_tokens(examples_block)},
            {"name": "history", "token_count": estimate_tokens(
                "\n".join(str(i.get("content") or "") for i in kept_history))},
            {"name": "world_info_at_depth", "token_count": estimate_tokens(world_at_depth)},
            {"name": "post_history", "token_count": estimate_tokens(post_history)},
        ]
        # 剧情模式三段：仅在真的产出内容时追加，老 1v1 的 segments 列表因此保持
        # 恰好 9 项且逐项数值不变（S5 快照契约）。
        segments.extend(self._story_segments(
            story_state_block, relations_rendered, cast_roster_block
        ))

        result = AssembledContext(
            messages=messages,
            prompt_text=prompt_text,
            segments=segments,
            world_info_trace=decisions,
            budget={
                "max_context_tokens": int(budget_cfg["max_context_tokens"]),
                "used_tokens": estimated,
                "reserve_for_output": int(budget_cfg["reserve_for_output"]),
                "available_tokens": total_budget,
                "history_budget": history_budget,
                "dropped_messages": dropped,
                "story_tokens": estimate_tokens(story_state_block),
                "relations_tokens": estimate_tokens(relations_rendered),
                "cast_tokens": estimate_tokens(cast_roster_block),
            },
            estimated_prompt_tokens=estimated,
            warnings=warnings,
            triggered_entry_ids=triggered_ids,
        )
        return result

    # ------------------------------------------------------------------ #
    # 剧情模式三段（S5）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _story_state_block(story_block: str, node_block: str, budget_cfg: dict[str, Any]) -> str:
        """拼装剧情状态段。

        契约：**永不因预算为零而整段丢弃** —— 剧情状态是「模型此刻必须知道的事实」，
        丢了会让角色说错话。改用硬截断到 `_STORY_HARD_CAP_TOKENS` 字符数上限来兜底。
        """
        parts = [p.strip() for p in (story_block, node_block) if p and p.strip()]
        if not parts:
            return ""
        merged = "\n".join(parts)
        cap_chars = _STORY_HARD_CAP_TOKENS * 2  # 中文约 2 字符/token，宽松留余量
        if len(merged) > cap_chars:
            merged = merged[:cap_chars].rstrip() + "…"
        return merged

    @staticmethod
    def _relations_rendered(
        relations_block: str, speaking_as: dict[str, Any] | None, budget_cfg: dict[str, Any]
    ) -> str:
        """关系图段：按预算裁剪（与 story_state 不同，关系可以丢几条不影响理解）。

        调用方若已用 `speaking_as` 裁剪出子图，这里只做预算兜底截断。
        """
        text = (relations_block or "").strip()
        if not text:
            return ""
        budget = int(budget_cfg["max_context_tokens"] * int(budget_cfg["relations_pct"]) / 100)
        if budget <= 0:
            return ""
        if estimate_tokens(text) <= budget:
            return text
        # 按行（每条关系一行）从前往后保留，直到预算耗尽
        kept: list[str] = []
        used = 0
        for line in text.splitlines():
            cost = estimate_tokens(line) + 1
            if kept and used + cost > budget:
                break
            kept.append(line)
            used += cost
        return "\n".join(kept)

    @staticmethod
    def _cast_roster_block(cast_roster: list[dict[str, Any]] | None) -> str:
        """在场角色一行摘要：`id（名字·身份）语气` —— 供模型正确引用 speaker id。"""
        if not cast_roster:
            return ""
        lines: list[str] = []
        for member in cast_roster[:12]:
            if not isinstance(member, dict):
                continue
            cid = str(member.get("id") or "").strip()
            if not cid:
                continue
            name = str(member.get("name") or cid)
            role = str(member.get("role") or "").strip()
            voice = str(member.get("voice") or "").strip()
            head = f"{cid}（{name}" + (f"·{role}" if role else "") + "）"
            lines.append(f"{head}：{voice}" if voice else head)
        if not lines:
            return ""
        return "【在场角色】\n" + "\n".join(lines)

    @staticmethod
    def _story_segments(
        story_state_block: str, relations_rendered: str, cast_roster_block: str
    ) -> list[dict[str, Any]]:
        """只把**真正有内容**的剧情段追加进 segments（空段不占列表位）。"""
        out: list[dict[str, Any]] = []
        for name, text in (
            ("story_state", story_state_block),
            ("relations", relations_rendered),
            ("cast_roster", cast_roster_block),
        ):
            if text.strip():
                out.append({"name": name, "token_count": estimate_tokens(text)})
        return out
    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    @staticmethod
    def _render(template: str, values: dict[str, str], warnings: list[str]) -> str:
        """占位符单遍替换；未知占位符原样保留并告警（防注入：不二次替换）。"""

        def _sub(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in values:
                return values[key]
            warnings.append("未知占位符 {{" + key + "}}，已原样保留。")
            return match.group(0)

        return _PLACEHOLDER_RE.sub(_sub, template or "")

    @staticmethod
    def _character_block(card: dict[str, Any]) -> str:
        lines: list[str] = []
        name = str(card.get("name") or "")
        if name:
            lines.append(f"# 角色：{name}")
        for label, key in (("设定", "description"), ("性格", "personality"), ("情境", "scenario")):
            text = str(card.get(key) or "").strip()
            if text:
                lines.append(f"{label}：{text}")
        return "\n".join(lines)

    @staticmethod
    def _examples_block(card: dict[str, Any], values: dict[str, str]) -> str:
        raw = str(card.get("mes_example") or "").strip()
        if not raw:
            return ""
        return "示例对话：\n" + ContextAssembler._render(raw, values, [])

    @staticmethod
    def _memory_block(memory: dict[str, Any]) -> str:
        parts: list[str] = []
        summary = str(memory.get("rolling_summary") or "").strip()
        if summary:
            parts.append(f"【前情摘要】{summary}")
        facts = memory.get("facts") or []
        if facts:
            rendered = "；".join(
                f"{f.get('key')}={f.get('value')}"
                for f in facts
                if isinstance(f, dict) and f.get("key")
            )
            if rendered:
                parts.append(f"【关键事实】{rendered}")
        return "\n".join(parts)

    def _run_world_info(
        self,
        worldbooks: list[dict[str, Any]],
        scan_text: str,
        budget_cfg: dict[str, Any],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        """把多本世界书合并後交给引擎裁决，汇总逐条 trace。"""
        # 世界书预算 = min(各书 token_budget 之和, 总预算 * world_info_pct)
        wi_pct = int(budget_cfg.get("world_info_pct", 25))
        wi_budget = int(budget_cfg["max_context_tokens"] * wi_pct / 100)
        merged_entries: list[dict[str, Any]] = []
        for book in worldbooks:
            merged_entries.extend(book.get("entries") or [])
        merged_book = {
            "entries": merged_entries,
            "token_budget": wi_budget,
            "recursive_scanning": any(bool(b.get("recursive_scanning")) for b in worldbooks),
            "scan_depth": max((int(b.get("scan_depth") or 4) for b in worldbooks), default=4),
            "max_recursion_depth": max(
                (int(b.get("max_recursion_depth") or 3) for b in worldbooks), default=3
            ),
        }
        result = self._world.test(merged_book, scan_text)
        # 引擎的 trace 不含正文，这里按 entry_id 回填 content 供拼块使用
        content_by_id = {
            str(e.get("id")): str(e.get("content") or "") for e in merged_entries if e.get("id")
        }
        decisions = list(result.get("entries") or [])
        for d in decisions:
            if "content" not in d:
                d["content"] = content_by_id.get(str(d.get("entry_id")), "")
            warnings.extend(d.get("warnings") or [])
        return decisions

    @staticmethod
    def _world_block(decisions: list[dict[str, Any]], positions: set[str]) -> str:
        """把命中且预算内的条目按最终位置拼成块。"""
        lines: list[str] = []
        for d in decisions:
            if not d.get("in_budget"):
                continue
            if d.get("final_position") in positions:
                content = str(d.get("content") or "").strip()
                if content:
                    lines.append(content)
        return "\n".join(lines)

    @staticmethod
    def _default_scan_text(history: list[dict[str, Any]], user_persona: dict[str, Any]) -> str:
        """默认扫描文本：最近若干条消息正文（世界书按关键词在对话上触发）。"""
        recent = history[-6:] if history else []
        return "\n".join(str(m.get("content") or "") for m in recent)

    @staticmethod
    def _trim_history(
        history: list[dict[str, Any]], budget: int
    ) -> tuple[list[dict[str, Any]], int]:
        """从最新往回保留直到超出预算，再反转为 oldest→newest。返回 (kept, dropped_count)。"""
        kept_reversed: list[dict[str, Any]] = []
        used = 0
        for item in reversed(history):
            cost = estimate_tokens(str(item.get("content") or "")) + 4
            if kept_reversed and used + cost > budget:
                break
            kept_reversed.append(item)
            used += cost
        kept = list(reversed(kept_reversed))
        return kept, max(0, len(history) - len(kept))


__all__ = ["AssembledContext", "ContextAssembler"]
