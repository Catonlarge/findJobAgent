"""
用户画像域模型 - 画像切片表
corresponds to Table 2 in database design document
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON

from enum import Enum

class ProfileSectionKey(str, Enum):
    """画像切片枚举值 - 核心枚举，确保业务逻辑分支的确定性"""
    SKILLS = "skills"
    WORK_EXPERIENCE = "work_experience"
    PROJECTS_SUMMARY = "projects_summary"
    PROJECT_DETAILS = "project_details"
    BEHAVIORAL_TRAITS = "behavioral_traits"
    EDUCATION = "education"
    SUMMARY = "summary"

class ProfileSection(SQLModel, table=True):
    """
    画像切片表
    存储用户的核心职业数据，Agent 运行时直接读取此表中预定义的 section_key 切片
    """
    __tablename__ = "profile_sections"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户，查询热点（Agent 初始化时拉取全量画像）
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # 核心枚举值，确保业务逻辑分支的确定性
    section_key: ProfileSectionKey = Field(nullable=False)

    # 复合唯一约束：确保每个用户每种类型的切片只有一个
    # 在 SQLModel 中通过 __table_args__ 定义

    # 切片内容，JSON 格式，直接存储该切片的所有数据
    content: Dict[str, Any] = Field(sa_column=Column(JSON))

    # 更新时间
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    class Config:
        # 定义复合唯一约束
        unique_together = ["user_id", "section_key"]
