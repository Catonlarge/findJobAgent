"""
用户域模型 - 用户索引表
corresponds to Table 1 in database design document
"""

from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON

from .base import TimestampModel

class User(TimestampModel, table=True):
    """
    用户索引表
    存储系统的绝对根节点，单机模式下默认为 "me"
    """
    __tablename__ = "users"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 唯一用户名，单机默认为 "me"
    # 唯一约束确保系统中不会出现重复用户
    username: str = Field(unique=True, index=True, nullable=False)

    # 基础信息 JSON（如姓名、城市等）
    # 使用 JSON 类型灵活存储用户基础信息，不需要严格表结构
    basic_info: Optional[Dict[str, Any]] = Field(default={}, sa_column=Column(JSON))
