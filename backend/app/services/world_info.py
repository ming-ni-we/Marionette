"""世界书触发引擎（产品护城河，架构 §4.4 / schemas.md §4.3）。

权威触发语义（不得偏离 schemas.md §4.3）：
  1. `constant=true` 无条件入选；
  2. 否则在扫描文本上匹配 `keys`：子串（可忽略大小写 / 整词）/ 正则；
  3. `selective=true` 需主关键词与次关键词各至少命中一条；
  4. `recursive_scanning=true` 时新入选条目的 content 并入扫描文本，深度硬上限 `max_recursion_depth`（防环）；
  5. 排序：`insertion_order` 升序；
  6. 预算裁决：累计 token 超过 `token_budget` 时按 `priority` 降序保留，低 priority 先被挤出。

**三态必须可区分**（AC-07 / AC-08）：
  - 未命中：`matched=false`
  - 命中且在预算内：`matched=true, in_budget=true`
  - 命中但被预算挤出：`matched=true, in_budget=false`（仍出现在结果里，绝不静默丢弃）

token 计数走 `services/tokens.py` 的保守估算（取大不取小），宁可误判挤出，也不让上游截断。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.tokens import estimate_tokens

logger = get_logger(__name__)

_REGEX_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}


def _flags_of(raw: str | None) -> int:
    flags = 0
    for ch in raw or "":
        flags |= _REGEX_FLAGS.get(ch, 0)
    return flags


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _literal_hit(needle: str, haystack: str, *, case_sensitive: bool, whole_words: bool) -> bool:
    if not needle:
        return False
    if not case_sensitive:
        needle, haystack = needle.lower(), haystack.lower()
    if whole_words:
        return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None
    return needle in haystack


@dataclass
class Decision:
    """单条条目的裁决结果。"""

    entry_id: str
    comment: str
    insertion_order: int
    priority: int
    position: str
    enabled: bool
    token_count: int
    matched: bool = False
    match_type: str = "none"
    matched_key: str | None = None
    in_budget: bool = False
    final_position: str | None = None
    note: str = ""
    warnings: list[str] = field(default_factory=list)


class WorldInfoEngine:
    """无状态触发引擎；`test()` 供命中测试端点消费（不落库）。"""

    def test(
        self, book: dict[str, Any] | None, sample_text: str, *, scan_depth: int | None = None
    ) -> dict[str, Any]:
        book = book if isinstance(book, dict) else {}
        items: list[tuple[str, dict[str, Any]]] = []
        for entry in book.get("entries") or []:
            if isinstance(entry, dict):
                items.append((str(entry.get("id") or uuid.uuid4()), entry))

        budget = int(book.get("token_budget") or 1024)
        effective_depth = int(scan_depth if scan_depth is not None else book.get("scan_depth") or 4)
        text = sample_text or ""

        decisions: dict[str, Decision] = {}
        for entry_id, entry in items:
            decisions[entry_id] = self._classify(entry_id, entry, text)

        if book.get("recursive_scanning"):
            self._recurse(items, text, decisions, int(book.get("max_recursion_depth") or 3))

        total = self._adjudicate(decisions, budget)

        matched = [d for d in decisions.values() if d.matched]
        ordered = sorted(decisions.values(), key=lambda d: (d.insertion_order, -d.priority, d.entry_id))
        return {
            "entries": [self._to_dict(d) for d in ordered],
            "total_tokens": total,
            "token_budget": budget,
            "matched_count": len(matched),
            "in_budget_count": sum(1 for d in decisions.values() if d.in_budget),
            "evicted_count": sum(1 for d in matched if not d.in_budget),
            "scan_depth": effective_depth,
        }

    # ---------------- 单条匹配 ----------------
    def _classify(self, entry_id: str, entry: dict[str, Any], text: str) -> Decision:
        content = str(entry.get("content") or "")
        decision = Decision(
            entry_id=entry_id,
            comment=str(entry.get("comment") or ""),
            insertion_order=int(entry.get("insertion_order") or 100),
            priority=int(entry.get("priority") or 10),
            position=str(entry.get("position") or "before_char"),
            enabled=bool(entry.get("enabled", True)),
            token_count=estimate_tokens(content),
        )
        if not decision.enabled:
            decision.note = "条目已禁用，不参与注入。"
            return decision
        if entry.get("constant"):
            decision.matched = True
            decision.match_type = "constant"
            decision.matched_key = "*"
            decision.note = "常驻条目：无条件注入（仍受预算约束）。"
            return decision

        hit = self._match_keys(_as_list(entry.get("keys")), text, entry, decision)
        if entry.get("selective"):
            if hit is None:
                decision.note = "selective 条目：主关键词未命中。"
                return decision
            secondary = self._match_keys(_as_list(entry.get("secondary_keys")), text, entry, decision)
            if secondary is None:
                decision.note = (
                    f"主关键词「{hit[0]}」已命中，但次级关键词均未命中，按 selective 规则不注入。"
                )
                return decision
            decision.matched = True
            decision.match_type, decision.matched_key = hit[1], hit[0]
            decision.note = "主/次关键词同时命中。"
            return decision

        if hit is None:
            if entry.get("vector_recall"):
                decision.note = "未命中关键词；该条目启用了向量召回，测试端点不计算 embedding，故此处不判定。"
            else:
                decision.note = "关键词/正则均未命中。"
            return decision
        decision.matched = True
        decision.match_type, decision.matched_key = hit[1], hit[0]
        return decision

    def _match_keys(
        self, keys: list[str], text: str, entry: dict[str, Any], decision: Decision
    ) -> tuple[str, str] | None:
        if not keys:
            return None
        case_sensitive = bool(entry.get("case_sensitive"))
        whole_words = bool(entry.get("match_whole_words"))
        use_regex = bool(entry.get("use_regex"))
        for key in keys:
            if not key:
                continue
            if use_regex:
                try:
                    if re.search(key, text, _flags_of(entry.get("regex_flags"))):
                        return key, "regex"
                    continue
                except re.error as exc:
                    decision.warnings.append(f"正则「{key}」编译失败（{exc}），已降级为字面匹配。")
            if _literal_hit(key, text, case_sensitive=case_sensitive, whole_words=whole_words):
                return key, "keyword"
        return None

    # ---------------- 递归扫描 ----------------
    def _recurse(
        self,
        items: list[tuple[str, dict[str, Any]]],
        base_text: str,
        decisions: dict[str, Decision],
        max_depth: int,
    ) -> None:
        """首轮扫描命中的内容并入扫描文本，再做最多 `max_depth` 轮递归（防环）。"""
        extra = "".join(
            "\n" + str(entry.get("content") or "")
            for entry_id, entry in items
            if decisions[entry_id].matched
        )
        for _ in range(max(0, max_depth)):
            progressed = False
            scan_text = base_text + extra
            for entry_id, entry in items:
                decision = decisions[entry_id]
                if decision.matched or not decision.enabled:
                    continue
                new = self._classify(entry_id, entry, scan_text)
                if new.matched:
                    decision.matched = True
                    decision.match_type = new.match_type
                    decision.matched_key = new.matched_key
                    decision.note = "经递归扫描（上游条目内容触发）命中。"
                    extra += "\n" + str(entry.get("content") or "")
                    progressed = True
            if not progressed:
                break

    # ---------------- 预算裁决 ----------------
    def _adjudicate(self, decisions: dict[str, Decision], budget: int) -> int:
        matched = [d for d in decisions.values() if d.matched]
        requested = sum(d.token_count for d in matched)
        if requested <= budget:
            for decision in matched:
                decision.in_budget = True
            return self._finalize(decisions, requested)

        # 超预算：按 priority 降序保留，低 priority 先被挤出
        ordered = sorted(matched, key=lambda d: (-d.priority, d.insertion_order, d.entry_id))
        accumulated = 0
        for decision in ordered:
            if accumulated + decision.token_count <= budget:
                decision.in_budget = True
                accumulated += decision.token_count
            else:
                decision.note = (
                    f"内容已命中，但累计 token 超出预算 {budget}，"
                    f"因 priority={decision.priority} 较低被挤出。"
                )
        return self._finalize(decisions, accumulated)

    @staticmethod
    def _finalize(decisions: dict[str, Decision], total: int) -> int:
        for decision in decisions.values():
            decision.final_position = decision.position if decision.in_budget else None
        return total

    @staticmethod
    def _to_dict(decision: Decision) -> dict[str, Any]:
        return {
            "entry_id": decision.entry_id,
            "comment": decision.comment,
            "matched": decision.matched,
            "match_type": decision.match_type,
            "matched_key": decision.matched_key,
            "in_budget": decision.in_budget,
            "token_count": decision.token_count,
            "final_position": decision.final_position,
            "priority": decision.priority,
            "insertion_order": decision.insertion_order,
            "enabled": decision.enabled,
            "note": decision.note,
            "warnings": decision.warnings,
        }


__all__ = ["Decision", "WorldInfoEngine"]
