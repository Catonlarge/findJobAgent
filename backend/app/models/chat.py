"""
会话域模型 - 业务会话表
corresponds to Table 4 in database design document
"""

from typing import Optional, Dict, Any
from sqlmodel import Field, Column, JSON

from enum import Enum

from .base import TimestampModel

class ChatIntent(str, Enum):
    """会话意图枚举 - 核心枚举值，决定 Router 走向"""
    RESUME_REFINE = "resume_refine"
    INTERVIEW_PREP = "interview_prep"
    GENERAL_CHAT = "general_chat"
    ONBOARDING = "onboarding"

class ChatSession(TimestampModel, table=True):
    """
    业务会话表
    对话的容器，管理 LangGraph 状态锚点
    """
    __tablename__ = "chat_sessions"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 业务主键：前端会话 UUID
    # 作用：对外暴露的会话 ID（URL 参数），安全且灵活
    # 优势：避免暴露自增 ID，支持前端路由（如 /chat/{session_uuid}）
    session_uuid: Optional[str] = Field(
        default=None,
        unique=True,
        index=True,
        description="Frontend-exposed session ID (URL-safe UUID)"
    )

    # 外键：归属用户，左侧栏会话列表查询
    # 索引优化：按用户查询会话列表时的性能
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # LangGraph Checkpoint ID
    # 唯一标识符，用于 LangGraph 的状态恢复
    thread_id: str = Field(unique=True, index=True, nullable=False)

    # 意图枚举，决定 Router 的走向
    # 核心业务逻辑分支点，影响 Agent 的处理流程
    intent: ChatIntent = Field(nullable=False)

    # 会话标题
    # UI 展示用，通常是用户的第一条消息摘要
    title: str = Field(nullable=False)

    # UI 环境配置 JSON（如 Persona）
    # 存储会话级别的配置，如用户角色、场景设定等
    context_data: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
