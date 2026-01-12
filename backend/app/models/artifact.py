"""
资产域模型 - 交付物表
corresponds to Table 7 in database design document
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON

from enum import Enum

class ArtifactType(str, Enum):
    """交付物类型枚举"""
    RESUME = "resume"
    ANALYSIS_REPORT = "analysis_report"
    COVER_LETTER = "cover_letter"

class MatchRating(str, Enum):
    """匹配度评级枚举（仅用于 analysis_report 类型）"""
    PERFECT_MATCH = "Perfect_Match"
    HIGH_MATCH = "High_Match"
    MEDIUM_MATCH = "Medium_Match"
    LOW_MATCH = "Low_Match"

class Artifact(SQLModel, table=True):
    """
    交付物表
    核心产出物，支持版本控制和并发安全
    """
    __tablename__ = "artifacts"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户
    user_id: int = Field(foreign_key="users.id", nullable=False)

    # 外键：来源追踪
    session_id: Optional[int] = Field(default=None, foreign_key="chat_sessions.id", index=True)

    # 外键：关联 JD
    jd_id: Optional[int] = Field(default=None, foreign_key="job_descriptions.id", index=True)

    # 组 ID：用于加载同一份简历的历史版本
    group_id: int = Field(index=True, nullable=False)

    # 版本号：并发安全锁，防止版本号冲突
    version: int = Field(nullable=False)

    # 复合唯一约束：group_id + version 组合唯一
    class Config:
        unique_together = ["group_id", "version"]

    # 交付物类型枚举
    type: ArtifactType = Field(nullable=False)

    # JSON 结构版本号（默认为 1）
    schema_version: int = Field(default=1, nullable=False)

    # 结构化内容 JSON
    # 若 type=analysis_report，内部可能包含 match_rating 枚举属性
    content: Dict[str, Any] = Field(sa_column=Column(JSON))

    # 列表摘要 JSON
    meta_summary: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))

    # 创建时间
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
