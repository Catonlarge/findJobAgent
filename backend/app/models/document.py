"""
文档归档域模型 - 原始归档表
corresponds to Table 3 in database design document
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

from enum import Enum

class DocumentType(str, Enum):
    """文档类型枚举"""
    RAW_RESUME = "raw_resume"
    JD_TEXT = "jd_text"
    BIOGRAPHY = "biography"

class Document(SQLModel, table=True):
    """
    原始归档表
    仅作为原始文件（PDF/Word）解析后的文本归档
    """
    __tablename__ = "documents"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # 文档类型枚举
    type: DocumentType = Field(nullable=False)

    # 巨型文本存储区
    content: str = Field(nullable=False)

    # 创建时间（按时间倒序排列）
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
