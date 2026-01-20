"""
用户画像域模型 - 画像切片表
corresponds to Table 2 in database design document
"""

from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import UniqueConstraint

from enum import Enum

from .base import TimestampModel

class ProfileSectionKey(str, Enum):
    """画像切片枚举值 - 核心枚举，确保业务逻辑分支的确定性"""
    SKILLS = "skills"
    WORK_EXPERIENCE = "work_experience"
    PROJECTS_SUMMARY = "projects_summary"
    PROJECT_DETAILS = "project_details"
    BEHAVIORAL_TRAITS = "behavioral_traits"
    EDUCATION = "education"
    SUMMARY = "summary"
    CAREER_POTENTIAL = "career_potential"  # 职业潜能与想法 (T2-01.2)

class ProfileSection(TimestampModel, table=True):
    """
    画像切片表
    存储用户的核心职业数据，Agent 运行时直接读取此表中预定义的 section_key 切片
    """
    __tablename__ = "profile_sections"

    # 定义复合唯一约束：确保每个用户每种类型的切片只有一个
    __table_args__ = (UniqueConstraint("user_id", "section_key", name="uix_user_section"),)

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户，查询热点（Agent 初始化时拉取全量画像）
    # 索引优化：按用户查询画像时的性能
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # 核心枚举值，确保业务逻辑分支的确定性
    # 使用 Enum 确保数据一致性，防止拼写错误
    section_key: ProfileSectionKey = Field(nullable=False)

    # 切片内容，JSON 格式，直接存储该切片的所有数据
    # 灵活存储结构化的职业数据，无需为每个字段创建列
    # 规范：content 内部键名应包含 source_l1_ids（证据链）
    content: Dict[str, Any] = Field(sa_column=Column(JSON))

    # 标签列：技能、角色等关键词（用于快速查询和筛选）
    # 示例：["Python", "Backend", "FastAPI"]
    # 优势：独立存储便于构建"技能云"或标签筛选功能
    tags: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Skill/role tags for filtering and search"
    )
