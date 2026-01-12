"""
会话域模型 - 业务会话表
corresponds to Table 4 in database design document
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON

from enum import Enum

class ChatIntent(str, Enum):
    """会话意图枚举 - 核心枚举值，决定 Router 走向"""
    RESUME_REFINE = "resume_refine"
    INTERVIEW_PREP = "interview_prep"
    GENERAL_CHAT = "general_chat"
    ONBOARDING = "onboarding"

class ChatSession(SQLModel, table=True):
    """
    业务会话表
    对话的容器，管理 LangGraph 状态锚点
    """
    __tablename__ = "chat_sessions"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户，左侧栏会话列表查询
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # LangGraph Checkpoint ID
    thread_id: str = Field(unique=True, index=True, nullable=False)

    # 意图枚举，决定 Router 的走向
    intent: ChatIntent = Field(nullable=False)

    # 会话标题
    title: str = Field(nullable=False)

    # UI 环境配置 JSON（如 Persona）
    context_data: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))

    # 排序热点：ORDER BY updated_at DESC
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
