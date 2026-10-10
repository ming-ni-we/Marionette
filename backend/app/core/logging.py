"""结构化日志。

选择 stdlib logging + 单行 key=value 格式：零额外依赖，容器 stdout 直接可读，
且便于后续接入任何日志采集器（不需要改代码）。
"""

from __future__ import annotations

import logging
import sys
from typing import Any

_CONFIGURED = False

_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class _KeyValueFormatter(logging.Formatter):
    """把 extra 里的键值对追加到行尾，形如：msg | key=value key2=value2"""

    _RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
        "message",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras: dict[str, Any] = {
            k: v for k, v in record.__dict__.items() if k not in self._RESERVED
        }
        if not extras:
            return base
        tail = " ".join(f"{k}={_stringify(v)}" for k, v in extras.items())
        return f"{base} | {tail}"


def _stringify(value: Any) -> str:
    text = str(value)
    if any(ch.isspace() for ch in text):
        return f'"{text}"'
    return text


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_KeyValueFormatter(_FMT))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper() or "INFO")
    # 降低噪音：容器里 uvicorn 的 access log 由反向代理日志替代
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
