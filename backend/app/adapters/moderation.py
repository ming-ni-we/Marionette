"""默认 ModerationProvider：基础词表 + 正则，可配置、可整体关闭（ADR-011）。

v1 不做本地分类模型（避免与显存争用、边际收益低）。
词表由运营/合规侧维护；命中即拦截并返回中性提示（不产生 LLM 调用）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.adapters.base import ModerationProvider, ModerationVerdict

# 默认基础词表（占位最小集，实际由配置覆盖：/api/v1/config/moderation -> rules.blocked_words）
DEFAULT_BLOCKED_WORDS: tuple[str, ...] = (
    "制作炸弹",
    "自制枪械",
    "儿童色情",
)


@dataclass
class ModerationSettings:
    enabled: bool = True
    check_input: bool = True
    check_output: bool = True
    provider: str = "builtin_wordlist"
    blocked_words: tuple[str, ...] = field(default_factory=lambda: DEFAULT_BLOCKED_WORDS)
    block_on_match: bool = True
    label_ai_generated: bool = True


class BuiltinWordlistModerationProvider(ModerationProvider):
    name = "builtin_wordlist"

    def __init__(self, settings: ModerationSettings | None = None) -> None:
        self.settings = settings or ModerationSettings()

    def _scan(self, text: str) -> ModerationVerdict:
        if not self.settings.enabled:
            return ModerationVerdict(blocked=False)
        if not text:
            return ModerationVerdict(blocked=False)
        lowered = text.lower()
        matched = tuple(w for w in self.settings.blocked_words if w and w.lower() in lowered)
        if matched and self.settings.block_on_match:
            return ModerationVerdict(
                blocked=True,
                matched=matched,
                message="输入内容未通过内容审核，请调整后再试。",
            )
        return ModerationVerdict(blocked=bool(matched), matched=matched)

    async def check_input(self, text: str) -> ModerationVerdict:
        if not self.settings.check_input:
            return ModerationVerdict(blocked=False)
        return self._scan(text)

    async def check_output(self, text: str) -> ModerationVerdict:
        if not self.settings.check_output:
            return ModerationVerdict(blocked=False)
        return self._scan(text)
