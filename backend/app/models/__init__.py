"""SQLAlchemy 模型集合。导入本包即完成全部表注册（Alembic autogenerate 依赖此行为）。"""

from app.models.app_config import AppConfig
from app.models.asset import Asset
from app.models.base import Base
from app.models.card import Card
from app.models.embedding import ContentEmbedding
from app.models.image_job import ImageJob
from app.models.memory_snapshot import MemorySnapshot
from app.models.message import Message
from app.models.preset import Preset
from app.models.session import Session
from app.models.worldbook import WorldBook

__all__ = [
    "AppConfig",
    "Asset",
    "Base",
    "Card",
    "ContentEmbedding",
    "ImageJob",
    "MemorySnapshot",
    "Message",
    "Preset",
    "Session",
    "WorldBook",
]
