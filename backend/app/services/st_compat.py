"""SillyTavern 兼容适配器（导入导出，schemas.md §3.4 / §4.4）。

职责：
  - 载体 -> JSON：交给 st_image.py（PNG/WEBP tEXt / .json）；
  - JSON -> 平台卡：V1 / V2 / V3 归一，未知字段保全（不销毁）；
  - 平台卡 -> ST V2：可回导（AC-06 的往返等价由 tests/test_st_compat.py 断言）。

世界书/条目的字段归一在 st_book.py。

保真度承诺（schemas.md §3.4 表）：
  ST V2 -> 平台 -> ST V2 除平台新增字段外逐字段一致（含未知键）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.core.config import SCHEMA_VERSIONS
from app.core.errors import BadRequestError
from app.schemas.content import CardData
from app.services.st_book import as_str_list, book_from_st, book_to_st
from app.services.st_image import read_card_payload, sniff_container

SCHEMA_VERSION_CARD = SCHEMA_VERSIONS["card"]

# data 节点中可被平台识别的字段（其余进 extensions.st_unknown.data）
_ST_CARD_FIELDS = {
    "name",
    "description",
    "personality",
    "scenario",
    "first_mes",
    "mes_example",
    "creator_notes",
    "system_prompt",
    "post_history_instructions",
    "alternate_greetings",
    "tags",
    "creator",
    "character_version",
    "extensions",
}
# V1 裸字段（无 spec 信封时据此判定 V1）
_V1_FIELDS = {"name", "description", "personality", "scenario", "first_mes", "mes_example"}
# 信封层已知键（不算"未知"）
_ST_ENVELOPE_KNOWN = _ST_CARD_FIELDS | {
    "spec",
    "spec_version",
    "data",
    "character_book",
    "avatar",
    "create_date",
}


def _validate_card_data(raw: dict[str, Any]) -> dict[str, Any]:
    """校验并归一化 data 节点；校验失败转 400（不得 500）。"""
    try:
        return CardData.model_validate(raw).model_dump(mode="json")
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ())) or "data"
        raise BadRequestError(
            f"卡片字段 {where} 不合法（{first.get('msg', '格式不正确')}），无法导入。"
        ) from exc


@dataclass
class CardImage:
    """导入时的头像载体（原始图片字节）。"""

    data: bytes
    content_type: str
    filename: str


@dataclass
class ParsedCard:
    payload: dict[str, Any]  # 平台 rpg_card 信封：{spec, spec_version, data, extensions}
    source_format: str  # st_v1 | st_v2 | st_v3 | native
    unknown_data: dict[str, Any] = field(default_factory=dict)
    unknown_envelope: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    image: CardImage | None = None
    original_id: str | None = None

    @property
    def unknown_keys(self) -> list[str]:
        keys = [f"data.{k}" for k in self.unknown_data]
        keys += [f"envelope.{k}" for k in self.unknown_envelope]
        return sorted(keys)


class STCompatAdapter:
    """ST <-> 平台 双向转换（无状态，可复用单例）。"""

    def parse_bytes(self, raw: bytes, *, filename: str = "") -> ParsedCard:
        """载体字节 -> 平台卡。PNG/WEBP 的原始图片同时作为头像。"""
        payload, keyword = read_card_payload(raw)
        parsed = self.parse_payload(payload)
        container = sniff_container(raw)
        if container in ("png", "webp"):
            parsed.image = CardImage(
                data=raw,
                content_type="image/png" if container == "png" else "image/webp",
                filename=filename or f"card.{container}",
            )
            if keyword not in ("chara", "ccv3"):
                parsed.warnings.append("卡片图片未带标准关键字，已按通用图片处理。")
        return parsed

    def parse_payload(self, payload: dict[str, Any]) -> ParsedCard:
        if not isinstance(payload, dict):
            raise BadRequestError("卡片内容必须是 JSON 对象。")
        spec = payload.get("spec")
        if spec == "rpg_card":
            return self._parse_native(payload)
        if spec in ("chara_card_v2", "chara_card_v3"):
            source = "st_v2" if spec == "chara_card_v2" else "st_v3"
            data = payload.get("data")
            if not isinstance(data, dict):
                raise BadRequestError(f"该卡声明为 {spec}，但缺少 data 节点，无法解析。")
            return self._from_st_data(data, source, payload)
        data = payload.get("data")
        if isinstance(data, dict) and any(k in data for k in _ST_CARD_FIELDS):
            return self._from_st_data(data, "st_v1", payload)
        if any(k in payload for k in _V1_FIELDS):
            return self._from_st_data(payload, "st_v1", payload)
        raise BadRequestError(
            "无法识别的角色卡格式：既不是 SillyTavern V1/V2/V3，也不是本平台的 rpg_card。"
            "请检查文件是否由 SillyTavern 或本平台导出。"
        )

    # ---------------- 内部 ----------------
    def _parse_native(self, payload: dict[str, Any]) -> ParsedCard:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise BadRequestError("rpg_card 缺少 data 节点，无法导入。")
        return ParsedCard(
            payload={
                "spec": "rpg_card",
                "spec_version": str(payload.get("spec_version") or SCHEMA_VERSION_CARD),
                "data": _validate_card_data(data),
                "extensions": payload.get("extensions") or {},
            },
            source_format="native",
        )

    def _from_st_data(
        self, data: dict[str, Any], source_format: str, envelope: dict[str, Any]
    ) -> ParsedCard:
        unknown_data: dict[str, Any] = {}
        out_data: dict[str, Any] = {}
        for key, value in data.items():
            if key == "character_book":
                out_data["character_book"] = book_from_st(value)
            elif key in _ST_CARD_FIELDS:
                out_data[key] = value
            else:
                unknown_data[key] = value

        unknown_envelope = {
            key: value for key, value in envelope.items() if key not in _ST_ENVELOPE_KNOWN
        }

        out_data["name"] = str(out_data.get("name") or "").strip()
        if not out_data["name"]:
            raise BadRequestError("该卡片没有角色名（data.name 为空），无法导入。")
        out_data["alternate_greetings"] = as_str_list(out_data.get("alternate_greetings"))
        out_data["tags"] = as_str_list(out_data.get("tags"))
        out_data["first_mes"] = str(out_data.get("first_mes") or "")
        out_data["description"] = str(out_data.get("description") or "")

        # 平台扩展：记录导入来源（schemas.md §3.2 data.extensions.rpg.source）
        rpg = dict((out_data.get("extensions") or {}).get("rpg") or {})
        rpg["source"] = {
            "format": source_format,
            "original_id": envelope.get("id") or None,
            "imported_at": datetime.now(UTC).isoformat(),
        }
        extensions_block = dict(out_data.get("extensions") or {})
        extensions_block["rpg"] = rpg
        out_data["extensions"] = extensions_block

        envelope_ext: dict[str, Any] = {}
        st_unknown = {
            k: v for k, v in (("data", unknown_data), ("envelope", unknown_envelope)) if v
        }
        if st_unknown:
            envelope_ext["st_unknown"] = st_unknown

        warnings: list[str] = []
        if unknown_data or unknown_envelope:
            warnings.append(
                f"已保留 {len(unknown_data) + len(unknown_envelope)} 个平台不认识的字段"
                "（存于 extensions.st_unknown，导出时原样写回）。"
            )
        if source_format == "st_v1":
            warnings.append("来源为 SillyTavern V1（裸字段），缺失字段已按默认值补齐。")
        if source_format == "st_v3":
            warnings.append("来源为 SillyTavern V3，V3 独有字段已保全但不参与渲染。")

        return ParsedCard(
            payload={
                "spec": "rpg_card",
                "spec_version": SCHEMA_VERSION_CARD,
                "data": _validate_card_data(out_data),
                "extensions": envelope_ext,
            },
            source_format=source_format,
            unknown_data=unknown_data,
            unknown_envelope=unknown_envelope,
            warnings=warnings,
            original_id=envelope.get("id") or None,
        )


def to_st_v2(card_payload: dict[str, Any]) -> dict[str, Any]:
    """平台卡信封 -> SillyTavern V2 JSON（可回导，AC-06）。"""
    data = dict(card_payload.get("data") or {})
    extensions = dict(card_payload.get("extensions") or {})
    st_unknown = dict(extensions.get("st_unknown") or {})

    st_data: dict[str, Any] = {}
    for key, value in data.items():
        if key == "character_book":
            st_data["character_book"] = book_to_st(value)
        elif key in _ST_CARD_FIELDS:
            st_data[key] = value
    st_data.setdefault("name", "")
    st_data.setdefault("description", "")
    st_data.setdefault("first_mes", "")
    st_data["tags"] = as_str_list(st_data.get("tags"))

    # 未识别的 data 键原样写回 data
    for key, value in (st_unknown.get("data") or {}).items():
        st_data.setdefault(key, value)

    st: dict[str, Any] = {"spec": "chara_card_v2", "spec_version": "2.0", "data": st_data}
    # 未识别的信封键原样写回顶层
    for key, value in (st_unknown.get("envelope") or {}).items():
        st.setdefault(key, value)
    return st


__all__ = ["CardImage", "ParsedCard", "STCompatAdapter", "to_st_v2"]
