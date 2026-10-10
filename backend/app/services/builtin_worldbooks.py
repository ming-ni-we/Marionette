"""内置示例世界书（首启向导）。内容必须真实可用，禁止占位文案。"""

from __future__ import annotations

from typing import Any


def build_entry(keys: list[str], content: str, comment: str, **kw: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": kw.pop("id", None),
        "keys": keys,
        "content": content,
        "comment": comment,
        "insertion_order": kw.pop("insertion_order", 100),
        "priority": kw.pop("priority", 10),
    }
    entry.update(kw)
    return {k: v for k, v in entry.items() if v is not None}


def build_book(
    name: str, description: str, entries: list[dict[str, Any]], tags: list[str], **kw: Any
) -> dict[str, Any]:
    return {
        "spec": "rpg_worldbook",
        "spec_version": "1.0",
        "data": {
            "name": name,
            "description": description,
            "scan_depth": kw.pop("scan_depth", 4),
            "token_budget": kw.pop("token_budget", 1024),
            "recursive_scanning": kw.pop("recursive_scanning", False),
            "max_recursion_depth": kw.pop("max_recursion_depth", 3),
            "entries": entries,
            "extensions": {"rpg": {"tags": tags, "owner_id": "local", "visibility": "private"}},
        },
        "extensions": {"rpg": {"builtin_sample": True}},
    }


def _city_book() -> dict[str, Any]:
    return build_book(
        "城南街区",
        "一组共享的现代都市日常设定：老城与新区交界的街区，生活节奏慢，四季分明。",
        [
            build_entry(
                ["城南", "街区", "城市"],
                "城南街区位于一座南方二线城市的旧城与新区的交界处。街上有开了二十年的五金店、"
                "修车铺和早餐摊，也有刚装修好的咖啡馆和共享自习室。地铁三号线穿过街区东侧，"
                "老菜市场在周末清晨最热闹。这里的人习惯放慢一点，陌生人之间也愿意搭两句话。",
                "街区总览（常驻）",
                constant=True,
                insertion_order=10,
                priority=100,
            ),
            build_entry(
                ["便利店", "夜班", "24小时"],
                "街区西口有一家 24 小时便利店，招牌的灯管有一节偶尔会闪。深夜时段客流量很少，"
                "店员大多是一个人值班，货架第二层的关东煮到凌晨会打折。店里有热水、微波炉，"
                "靠窗有一个对着街道的单人高脚桌。",
                "便利店",
                insertion_order=100,
            ),
            build_entry(
                ["天台", "楼顶"],
                "街区里的居民楼大多是六到八层。顶层天台没有统一管理，晾衣绳、旧花盆和几张塑料凳"
                "是常见配置。傍晚风向合适的时候，能听见远处高架的车流声，也能看见一点点夕阳。",
                "居民楼天台",
                insertion_order=110,
            ),
            build_entry(
                ["江边", "步道", "堤岸"],
                "从街区往南走十五分钟就是江边。沿江修了步道和低矮护栏，夜里路灯偏暖色，"
                "跑步的人和不说话的人各占一半。江对岸是新区的高楼，夜里灯火成片。",
                "江边步道",
                insertion_order=120,
            ),
            build_entry(
                ["下雨", "梅雨", "天气"],
                "这一带每年五到七月是梅雨季，雨不大但下得久，地面总是半干不湿。"
                "本地人出门习惯在包里放一把折叠伞，便利店门口常年摆着湿伞架。",
                "天气：梅雨",
                insertion_order=130,
            ),
        ],
        ["现代", "都市", "日常"],
    )


def _daily_book() -> dict[str, Any]:
    return build_book(
        "日常向对话基调",
        "约束角色的表达方式，让互动保持现代日常感，避免脱离生活的夸张设定。",
        [
            build_entry(
                ["日常", "基调"],
                "这是一个没有超能力的现代世界。角色是普通职业的普通人：会加班、会为了几块钱"
                "犹豫、会记住别人随口说过的话。对话以生活细节推进，情绪克制但真诚，"
                "不写宏大叙事，也不替用户决定他的想法。",
                "内容基调（常驻）",
                constant=True,
                insertion_order=10,
                priority=120,
            ),
            build_entry(
                ["称呼", "名字"],
                "角色默认称呼用户为「你」，在关系熟悉后可使用用户告知的名字。"
                "若用户设定过自己的名字（user_persona.name），优先使用该名字。",
                "称呼约定",
                insertion_order=200,
            ),
        ],
        ["基调", "写作规范"],
    )


def sample_worldbooks() -> list[dict[str, Any]]:
    return [_city_book(), _daily_book()]


__all__ = ["build_book", "build_entry", "sample_worldbooks"]
