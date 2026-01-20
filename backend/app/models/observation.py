"""
用户画像域模型 - 原始观察缓冲区 (L1)
corresponds to Table 2.5 in database design document
"""

from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from enum import Enum

from .base import TimestampModel

# 1. 定义状态枚举 (遵循设计原则 5: 枚举严格)
class ObservationStatus(str, Enum):
    PENDING = "pending"
    PROMOTED = "promoted"  # 已写入 profile_sections
    REJECTED = "rejected"  # 用户在提案阶段拒绝
    MERGED = "merged"

# 2. 定义分类枚举
class ObservationCategory(str, Enum):
    SKILL = "skill_detect"
    TRAIT = "trait_detect"
    EXPERIENCE = "experience_fragment"
    PREFERENCE = "preference"


class RawObservation(TimestampModel, table=True):
    """
    原始观察缓冲区 (L1)
    AI 的"便签本"，存储 Shadow Extractor 捕捉的未经确认的"泥沙"数据
    """
    __tablename__ = "raw_observations"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # 血缘追踪：指向具体的哪一条聊天记录
    source_message_id: Optional[int] = Field(
        default=None,
        foreign_key="chat_messages.id",
        index=True
    )

    # 观察分类
    category: ObservationCategory = Field(nullable=False)

    # 具体观察内容
    fact_content: str = Field(nullable=False)

    # 置信度：1-100，用于提案节点过滤
    confidence: int = Field(ge=0, le=100, default=50)

    # 潜力标记：True=微弱信号(如"帮同事倒垃圾"->服务意识)
    is_potential_signal: bool = Field(default=False, nullable=False)

    # 核心状态流转字段
    status: ObservationStatus = Field(
        default=ObservationStatus.PENDING,
        index=True,
        nullable=False
    )

    # 上下文快照，使用 JSON 存储
    context_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON)
    )
