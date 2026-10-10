"""记忆与摘要服务（架构 §4.5）。

三段结构：
  A. 滚动摘要：把「已摘要窗口」之前的对话压缩成一段叙述 —— 由 LLM 定期压缩；
  B. 关键事实：结构化 key-value —— LLM 抽取 + **正则兜底**（v1 默认打开）；
  C. 向量召回：按语义相似度取片段 —— v1 默认关闭（embedding 链路后续接入）。

本轮交付**最小可用骨架**：
  - extract_facts()：正则从消息里抽取「玩家名字/年龄/物品/地点/关系」等关键事实；
  - merge_facts()：按 key 去重合并（新值覆盖旧值，保留 confidence 较高者）；
  - should_summarize()：判断未摘要历史 token 是否超过历史预算阈值（默认 80%）；
  - build_block()：把 A+B 渲染成给 ContextAssembler 的长期记忆块。

LLM 摘要接口 `summarize_with_llm()` 先留签名（raise NotImplementedError 前的钩子），
避免本轮引入未验证的上游调用；接入点已就绪，后续只需填实现。

分层铁律：只依赖纯函数与 tokens 估算，不 import FastAPI / 厂商 SDK。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.services.tokens import estimate_tokens

logger = get_logger(__name__)

# 默认历史预算占比阈值（未摘要历史超过历史预算该比例即触发摘要）
DEFAULT_SUMMARY_TRIGGER_RATIO = 0.8

# ---- 关键事实正则抽取规则（中文日常向；命中即作为兜底事实）----
# 每条规则：命名组 key 用固定名，抽取 value。
_FACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("玩家姓名", re.compile(r"我(?:的名字)?叫([^\s，。,.！!？?]{1,12})")),
    ("玩家姓名", re.compile(r"我的名字是([^\s，。,.！!？?]{1,12})")),
    ("玩家年龄", re.compile(r"我(?:今年)?(\d{1,2})\s*岁")),
    ("获得物品", re.compile(r"(?:我)?(?:拿到了|得到|拿起|获得)了?(?:一个|一把|一件|一枚)?([^\s，。,.！!？?]{1,16})")),
    ("所在地点", re.compile(r"(?:我在|来到|抵达|身处)([^\s，。,.！!？?]{1,16})")),
)


@dataclass
class MemoryBlock:
    """长期记忆块（A + B）。"""

    rolling_summary: str = ""
    facts: list[dict[str, Any]] = field(default_factory=list)

    def render(self) -> str:
        parts: list[str] = []
        if self.rolling_summary.strip():
            parts.append(f"【前情摘要】{self.rolling_summary.strip()}")
        if self.facts:
            rendered = "；".join(
                f"{f['key']}={f['value']}" for f in self.facts if f.get("key") and f.get("value")
            )
            if rendered:
                parts.append(f"【关键事实】{rendered}")
        return "\n".join(parts)


class MemorySvc:
    """滚动摘要（段 A）+ 关键事实（段 B）；段 C 向量召回 v1 默认关闭。"""

    def __init__(self, db: Any | None = None) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    # 关键事实：正则兜底抽取
    # ------------------------------------------------------------------ #
    @staticmethod
    def extract_facts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """从消息列表里用正则抽取关键事实（仅扫 user 消息，避免把角色台词当玩家事实）。"""
        facts: list[dict[str, Any]] = []
        for msg in messages:
            if str(msg.get("role")) != "user":
                continue
            text = str(msg.get("content") or "")
            if not text:
                continue
            for key, pattern in _FACT_PATTERNS:
                match = pattern.search(text)
                if not match:
                    continue
                value = match.group(1).strip()
                if not value:
                    continue
                facts.append(
                    {
                        "key": key,
                        "value": value,
                        "confidence": 0.6,  # 正则兜底置信度低于 LLM 抽取
                        "source_message_id": str(msg.get("id") or "") or None,
                        "updated_at": datetime.now(UTC),
                    }
                )
        return facts

    @staticmethod
    def merge_facts(
        existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """按 key 合并：新值覆盖旧值，但 confidence 取两者较大者（保守保留高置信）。"""
        merged: dict[str, dict[str, Any]] = {}
        for fact in list(existing) + list(incoming):
            key = str(fact.get("key") or "")
            if not key or not fact.get("value"):
                continue
            prev = merged.get(key)
            if prev is None:
                merged[key] = dict(fact)
                continue
            winner = dict(fact)
            winner["confidence"] = max(
                float(prev.get("confidence") or 0), float(fact.get("confidence") or 0)
            )
            merged[key] = winner
        return list(merged.values())

    # ------------------------------------------------------------------ #
    # 触发判定
    # ------------------------------------------------------------------ #
    @staticmethod
    def should_summarize(
        messages: list[dict[str, Any]],
        *,
        summary_upto_message_id: str | None,
        history_budget: int,
        trigger_ratio: float = DEFAULT_SUMMARY_TRIGGER_RATIO,
    ) -> bool:
        """未摘要历史的 token 是否已达历史预算的触发比例。"""
        if history_budget <= 0:
            return False
        seen_upto = summary_upto_message_id is None
        unsorted = 0
        for msg in messages:
            if not seen_upto:
                if str(msg.get("id")) == summary_upto_message_id:
                    seen_upto = True
                continue
            unsorted += estimate_tokens(str(msg.get("content") or ""))
        return unsorted >= history_budget * trigger_ratio

    # ------------------------------------------------------------------ #
    # 摘要（LLM 留接口）
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_rolling_summary(existing_summary: str, messages: list[dict[str, Any]]) -> str:
        """无 LLM 时的确定性兜底摘要：把消息首句串成叙述，保证有内容可注入。

        说明：这是**降级实现**，质量低于 LLM 摘要；接入 LLM 后由 summarize_with_llm 覆盖。
        """
        snippets: list[str] = []
        for msg in messages:
            text = str(msg.get("content") or "").strip().replace("\n", " ")
            if not text:
                continue
            snippets.append(text[:40])
        appended = " / ".join(snippets)
        if not appended:
            return existing_summary
        if existing_summary:
            return f"{existing_summary} {appended}"
        return appended

    async def summarize_with_llm(self, *args: Any, **kwargs: Any) -> str:
        """LLM 摘要接入点（本轮留空实现，走 build_rolling_summary 兜底后即可上线）。

        接入方式：用 LLMRouter.stream 把「最老一批未摘要消息」提要成一段叙述，
        推进 summary_upto_message_id 并写入 memory_snapshots 版本行。
        """
        raise NotImplementedError("LLM 摘要将在后续轮次接入；当前使用正则与单句拼接兜底。")

    # ------------------------------------------------------------------ #
    # 组装长期记忆块
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_block(memory: dict[str, Any]) -> MemoryBlock:
        facts = [f for f in (memory.get("facts") or []) if isinstance(f, dict)]
        # 超限时按 confidence 降序保留（与 §4.5 裁剪顺序一致）
        facts.sort(key=lambda f: float(f.get("confidence") or 0), reverse=True)
        return MemoryBlock(
            rolling_summary=str(memory.get("rolling_summary") or ""),
            facts=facts,
        )


__all__ = ["DEFAULT_SUMMARY_TRIGGER_RATIO", "MemoryBlock", "MemorySvc"]
