"""埋点与诊断服务（F10 / SPEC §4.10）。

设计要点：
  - **仅落本地**：事件以 JSONL 追加写入 `./data/telemetry/events.jsonl`，绝不上报云端。
  - **隐私优先（SPEC §10）**：不采集原始输入内容，不回写 IP；properties 只做浅层
    白名单化长度截断，避免超长/敏感正文入库。
  - **诊断包**：打包本地日志 + 自检结果 + 配置快照（脱敏）为 zip，供用户一键导出。

分层铁律：本服务不 import 任何厂商 SDK；自检复用 core/db 与适配器接口。
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# 事件名允许的最大长度 & properties 值截断长度（防脏数据撑爆本地文件）
MAX_EVENT_NAME_LEN = 128
MAX_PROP_VALUE_LEN = 512
# 诊断包内最多保留的近期事件条数
DIAGNOSTIC_EVENT_TAIL = 500
# 日志目录内单文件最多纳入的字节数（防诊断包过大）
MAX_LOG_BYTES = 2 * 1024 * 1024


def telemetry_dir() -> Path:
    """埋点落盘目录（与 config_dir 同级，便于随实例数据目录一起管理）。"""
    settings = get_settings()
    base = Path(settings.config_dir).parent
    return base / "telemetry"


def events_file() -> Path:
    return telemetry_dir() / "events.jsonl"


def _sanitize_properties(props: dict[str, Any]) -> dict[str, Any]:
    """浅层脱敏：仅保留标量/短容器，值超长即截断；键超长丢弃。"""
    clean: dict[str, Any] = {}
    for key, value in (props or {}).items():
        k = str(key)
        if len(k) > MAX_EVENT_NAME_LEN:
            continue
        if isinstance(value, str):
            clean[k] = value[:MAX_PROP_VALUE_LEN]
        elif isinstance(value, (int, float, bool)) or value is None:
            clean[k] = value
        elif isinstance(value, (list, tuple)):
            clean[k] = [
                v[:MAX_PROP_VALUE_LEN] if isinstance(v, str) else v
                for v in list(value)[:20]
            ]
        else:
            # 嵌套对象不落库，避免携带任意结构
            clean[k] = f"<{type(value).__name__}>"
    return clean


class TelemetrySvc:
    """本地匿名事件记录 + 诊断包导出。"""

    def __init__(self, *, directory: Path | None = None) -> None:
        self._dir = directory

    def _dir_path(self) -> Path:
        return self._dir or telemetry_dir()

    def _events_path(self) -> Path:
        return self._dir_path() / "events.jsonl"

    def record(self, name: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
        """追加一条事件到本地 JSONL。返回落库后的条目（含服务端时间戳）。"""
        clean_name = str(name or "").strip()[:MAX_EVENT_NAME_LEN]
        entry = {
            "name": clean_name,
            "properties": _sanitize_properties(properties or {}),
            "ts": datetime.now(UTC).isoformat(),
        }
        path = self._events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("telemetry event", extra={"event": clean_name})
        return entry

    def read_events(self, *, limit: int = DIAGNOSTIC_EVENT_TAIL) -> list[dict[str, Any]]:
        """读取最近的若干事件（用于诊断包）。文件不存在或损坏时返回空列表。"""
        path = self._events_path()
        if not path.is_file():
            return []
        events: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:  # noqa: BLE001 —— 读取失败不阻断诊断导出
            logger.warning("read telemetry failed: %s", type(exc).__name__)
            return []
        return events[-limit:]

    # ------------------------------------------------------------------ #
    # 诊断包
    # ------------------------------------------------------------------ #
    async def build_diagnostics(
        self, *, checks: Iterable[dict[str, Any]] | None = None
    ) -> bytes:
        """打包诊断 zip 字节流：自检结果 + 配置快照（脱敏）+ 近期事件 + 本地日志。"""
        payload = await self._collect(checks=checks)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "summary.json", json.dumps(payload, ensure_ascii=False, indent=2)
            )
            # 事件单独成文件，便于用工具查看
            zf.writestr(
                "events.jsonl",
                "\n".join(json.dumps(e, ensure_ascii=False) for e in payload["events"]),
            )
            for name, content in payload["logs"].items():
                zf.writestr(f"logs/{name}", content)
        return buffer.getvalue()

    async def _collect(
        self, *, checks: Iterable[dict[str, Any]] | None
    ) -> dict[str, Any]:
        settings = get_settings()
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "app_version": settings.app_version,
            "app_env": settings.app_env,
            "checks": list(checks or []),
            "config_snapshot": await self._config_snapshot(settings),
            "events": self.read_events(),
            "logs": _read_logs(self._dir_path()),
        }

    @staticmethod
    async def _config_snapshot(settings: Any) -> dict[str, Any]:
        """配置快照（**必须脱敏**：只含开关与非敏感字段，绝不含 api_key/口令）。"""
        return {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "llm_base_url_configured": bool(settings.llm_base_url),
            "image_provider": settings.image_provider,
            "image_model": settings.image_model,
            "image_base_url_configured": bool(settings.image_base_url),
            "database_url_configured": bool(settings.database_url),
            "domain": settings.domain,
            "log_level": settings.log_level,
            "cors_origins": settings.cors_origin_list,
        }


def _read_logs(directory: Path) -> dict[str, str]:
    """读取 data/logs 下的文本日志（若存在），单文件截断到 MAX_LOG_BYTES。"""
    logs: dict[str, str] = {}
    log_dir = directory.parent / "logs"
    if not log_dir.is_dir():
        return logs
    for path in sorted(log_dir.glob("*.log")):
        try:
            data = path.read_bytes()[-MAX_LOG_BYTES:]
            logs[path.name] = data.decode("utf-8", errors="replace")
        except OSError:
            continue
    return logs


__all__ = [
    "DIAGNOSTIC_EVENT_TAIL",
    "TelemetrySvc",
    "events_file",
    "telemetry_dir",
]
