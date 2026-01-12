"""
资产域模型 - JD 独立表
corresponds to Table 6 in database design document
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON

class JobDescription(SQLModel, table=True):
    """
    JD 独立表
    存储职位描述的独立表，支持 JD 管理列表功能
    """
    __tablename__ = "job_descriptions"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户，JD 管理列表查询
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # 岗位名称
    title: str = Field(nullable=False)

    # 公司名称
    company: Optional[str] = Field(default=None)

    # JD 原始全文
    raw_content: str = Field(nullable=False)

    # 结构化标签 JSON（可选）
    parsed_tags: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))

    # 创建时间（按创建时间倒序）
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
