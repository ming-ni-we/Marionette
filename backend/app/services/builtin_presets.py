"""内置默认预设（首启向导）：日常向、默认不出图。"""

from __future__ import annotations

from typing import Any


def _preset() -> dict[str, Any]:
    return {
        "spec": "rpg_preset",
        "spec_version": "1.0",
        "data": {
            "name": "日常向默认预设",
            "description": "适合现代日常角色扮演：克制的温度、稳定的文风、默认不出图。",
            "sampling": {
                "temperature": 0.85,
                "top_p": 0.95,
                "top_k": 40,
                "min_p": 0.05,
                "repetition_penalty": 1.08,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "max_tokens": 900,
                "seed": -1,
                "stop": [],
            },
            "prompt_template": {
                "system": (
                    "你正在扮演 {{char}}。请始终以 {{char}} 的身份与用户 {{user}} 进行现代日常向对话。\n"
                    "设定：{{description}}\n性格：{{personality}}\n当前情境：{{scenario}}\n"
                    "{{world_info}}{{memory}}\n"
                    "要求：保持人物一致性；用具体的动作与生活细节代替空泛抒情；"
                    "不替用户决定他的言行；不主动跳出角色解释自己。"
                ),
                "instruction": "以 {{char}} 的口吻回复，篇幅自然，不堆砌形容词。",
                "chat_separator": "\n",
                "placeholders": {},
            },
            "context_budget": {
                "max_context_tokens": 8192,
                "reserve_for_output": 1024,
                "character_pct": 15,
                "world_info_pct": 25,
                "memory_pct": 15,
                "vector_recall_pct": 5,
                "history_pct": 35,
            },
            "memory": {
                "summarize_every_n_turns": 10,
                "summary_trigger_ratio": 0.8,
                "vector_top_k": 5,
                "extract_facts": True,
            },
            "image_hook": {
                "enabled": False,
                "mode": "manual",
                "every_n_turns": 10,
                "workflow_template_id": None,
            },
            "extensions": {"rpg": {"owner_id": "local", "visibility": "private"}},
        },
        "extensions": {"rpg": {"builtin_sample": True}},
    }


def sample_presets() -> list[dict[str, Any]]:
    return [_preset()]


__all__ = ["sample_presets"]
