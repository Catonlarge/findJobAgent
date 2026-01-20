"""
数据库模型模块
导出所有表模型和枚举类型
"""

# 用户域模型
from .user import User
from .profile import ProfileSection, ProfileSectionKey
from .observation import RawObservation, ObservationStatus, ObservationCategory
from .document import Document, DocumentType

# 会话域模型
from .chat import ChatSession, ChatIntent
from .message import ChatMessage, MessageRole, UserFeedback

# 资产域模型
from .job import JobDescription
from .artifact import Artifact, ArtifactType, MatchRating

# 基础模型
from .base import TimestampModel

# 定义导出的内容
__all__ = [
    # 用户域
    "User",
    "ProfileSection", "ProfileSectionKey",
    "RawObservation", "ObservationStatus", "ObservationCategory",
    "Document", "DocumentType",
    # 会话域
    "ChatSession", "ChatIntent",
    "ChatMessage", "MessageRole", "UserFeedback",
    # 资产域
    "JobDescription",
    "Artifact", "ArtifactType", "MatchRating",
    # 基础模型
    "TimestampModel"
]
