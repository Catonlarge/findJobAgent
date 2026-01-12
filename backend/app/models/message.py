"""
会话域模型 - 消息流水表
corresponds to Table 5 in database design document
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON

from enum import Enum

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

class ChatMessage(SQLModel, table=True):
    """
    消息流水表
    记录对话流，包含 CoT 存储区和用户反馈
    """
    __tablename__ = "chat_messages"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：会话ID，查询热点（加载当前会话的所有消息）
    session_id: int = Field(foreign_key="chat_sessions.id", index=True, nullable=False)

    # 消息角色：user, assistant, system
    role: MessageRole = Field(nullable=False)

    # CoT 存储区：存储 <think> 标签内容
    thought_process: Optional[str] = Field(default=None)

    # 回复内容
    content: str = Field(nullable=False)

    # 关联交付物 ID（用于渲染卡片）
    related_artifact_id: Optional[int] = Field(default=None, foreign_key="artifacts.id", index=True)

    # 用户反馈：like, dislike, correction
    user_feedback: Optional[UserFeedback] = Field(default=None)

    # 成本统计：token 数量
    token_count: Optional[int] = Field(default=None)

    # 创建时间
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
