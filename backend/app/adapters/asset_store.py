"""默认 AssetStore：服务器本地卷（./data/assets）。

存储键（storage_key）是相对路径，不是绝对路径——换成对象存储时 key 语义不变，
数据库里的 assets.storage_key 无需改写（ADR-009）。
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.adapters.base import AssetStore, StoredObject
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

_EXT_BY_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class LocalAssetStore(AssetStore):
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    # ---------------- 内部 ----------------
    def _resolve(self, storage_key: str) -> Path:
        """把存储键解析为绝对路径，并阻断目录穿越。"""
        key = storage_key.strip().lstrip("/\\")
        candidate = (self._root / key).resolve()
        root = self._root.resolve()
        if root != candidate and root not in candidate.parents:
            raise AppError("非法的资产存储键。", code=4000, http_status=400)
        return candidate

    @staticmethod
    def _ext_for(filename: str, content_type: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix:
            return suffix
        return _EXT_BY_TYPE.get(content_type, ".bin")

    def _write(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _read(self, path: Path) -> bytes:
        return path.read_bytes()

    # ---------------- 接口 ----------------
    async def save(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
        kind: str = "gallery",
    ) -> StoredObject:
        ext = self._ext_for(filename, content_type)
        import datetime as _dt

        today = _dt.datetime.now(_dt.UTC)
        key = f"{kind}/{today:%Y/%m}/{uuid.uuid4()}{ext}"
        path = self._resolve(key)
        await asyncio.to_thread(self._write, path, data)
        logger.info("asset stored", extra={"storage_key": key, "size": len(data)})
        return StoredObject(storage_key=key, size_bytes=len(data))

    async def read(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        if not path.is_file():
            raise AppError("资产文件不存在。", code=4040, http_status=404)
        return await asyncio.to_thread(self._read, path)

    async def delete(self, storage_key: str) -> bool:
        path = self._resolve(storage_key)
        if not path.is_file():
            return False
        await asyncio.to_thread(path.unlink)
        return True

    async def exists(self, storage_key: str) -> bool:
        return await asyncio.to_thread(self._resolve(storage_key).is_file)
