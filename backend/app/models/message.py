"""
会话域模型 - 消息流水表
corresponds to Table 5 in database design document
"""

from typing import Optional
from sqlmodel import Field

from enum import Enum

from .base import TimestampModel

class MessageRole(str, Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class UserFeedback(str, Enum):
    """用户反馈枚举"""
    LIKE = "like"
    DISLIKE = "dislike"
    CORRECTION = "correction"

class ChatMessage(TimestampModel, table=True):
    """
    消息流水表
    记录对话流，包含 CoT 存储区和用户反馈
    """
    __tablename__ = "chat_messages"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：会话ID，查询热点（加载当前会话的所有消息）
    # 索引优化：按会话查询消息时的性能
    session_id: int = Field(foreign_key="chat_sessions.id", index=True, nullable=False)

    # 消息角色：user, assistant, system
    # 用于区分消息来源，影响 UI 展示和权限控制
    role: MessageRole = Field(nullable=False)

    # CoT 存储区：存储 <think> 标签内容
    # Agent 的思维过程记录，用于调试和可解释性
    thought_process: Optional[str] = Field(default=None)

    # 回复内容
    # 实际展示给用户的文本内容
    content: str = Field(nullable=False)

    # 关联交付物 ID（用于渲染卡片）
    # 当消息包含交付物时，关联到 artifact 表
    related_artifact_id: Optional[int] = Field(default=None, foreign_key="artifacts.id", index=True)

    # 用户反馈：like, dislike, correction
    # 用于收集用户反馈，优化模型表现
    user_feedback: Optional[UserFeedback] = Field(default=None)

    # 成本统计：token 数量
    # 用于成本追踪和计费
    token_count: Optional[int] = Field(default=None)
