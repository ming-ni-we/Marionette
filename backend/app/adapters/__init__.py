"""适配层：五类可替换接缝的接口与默认实现。"""

from app.adapters.base import (
    AssetStore,
    AuthProvider,
    ChatMessage,
    GeneratedImage,
    ImageProvider,
    LLMHealth,
    LLMProvider,
    LoginOutcome,
    ModerationProvider,
    ModerationVerdict,
    StoredObject,
)

__all__ = [
    "AssetStore",
    "AuthProvider",
    "ChatMessage",
    "GeneratedImage",
    "ImageProvider",
    "LLMHealth",
    "LLMProvider",
    "LoginOutcome",
    "ModerationProvider",
    "ModerationVerdict",
    "StoredObject",
]
