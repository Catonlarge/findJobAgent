"""
基础数据库配置模块
提供所有模型共用的基础类和数据库连接配置
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field

# 全局基础模型，包含创建和更新时间戳
class TimestampModel(SQLModel):
    """时间戳基类，为所有模型提供 created_at 和 updated_at 字段

    使用 timezone-aware datetime 替代已弃用的 utcnow()
    """
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)}
    )
