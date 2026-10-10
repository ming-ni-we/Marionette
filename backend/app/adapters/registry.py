"""适配器工厂：按配置组装默认实现，进程内单例。

业务层通过这里的 get_* 取接口，永远不直接 new 具体实现，
这样二期换实现（对象存储 / 云审核 / JWT）只改本文件。
"""

from __future__ import annotations

from functools import lru_cache

from app.adapters.auth import PasswordAuthProvider
from app.adapters.base import (
    AssetStore,
    AuthProvider,
    ImageProvider,
    LLMProvider,
    ModerationProvider,
)
from app.adapters.image import CloudImageProvider, LocalComfyUIProvider
from app.adapters.llm import OpenAICompatibleLLMProvider
from app.adapters.moderation import BuiltinWordlistModerationProvider
from app.adapters.asset_store import LocalAssetStore
from app.core.config import get_settings
from app.core.security import AccessControl


@lru_cache(maxsize=1)
def get_access_control() -> AccessControl:
    s = get_settings()
    return AccessControl(
        password=s.access_password,
        secret_key=s.secret_key,
        ttl_seconds=s.session_ttl_seconds,
        max_failed=s.access_max_failed,
        lock_window_seconds=s.access_lock_window_seconds,
    )


@lru_cache(maxsize=1)
def get_auth_provider() -> AuthProvider:
    return PasswordAuthProvider(get_access_control())


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    s = get_settings()
    return OpenAICompatibleLLMProvider(
        timeout_seconds=s.llm_timeout_seconds,
        test_timeout_seconds=s.llm_test_timeout_seconds,
    )


@lru_cache(maxsize=1)
def get_image_provider() -> ImageProvider:
    s = get_settings()
    if s.image_provider == "local_comfyui":
        return LocalComfyUIProvider()
    return CloudImageProvider(
        base_url=s.image_base_url,
        api_key=s.image_api_key,
        model=s.image_model,
    )


@lru_cache(maxsize=1)
def get_asset_store() -> AssetStore:
    return LocalAssetStore(get_settings().assets_dir)


@lru_cache(maxsize=1)
def get_moderation_provider() -> ModerationProvider:
    return BuiltinWordlistModerationProvider()
