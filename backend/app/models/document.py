"""
文档归档域模型 - 原始归档表
corresponds to Table 3 in database design document
"""

from typing import Optional
from sqlmodel import SQLModel, Field

from enum import Enum

from .base import TimestampModel

class DocumentType(str, Enum):
    """文档类型枚举"""
    RAW_RESUME = "raw_resume"
    JD_TEXT = "jd_text"
    BIOGRAPHY = "biography"

class Document(TimestampModel, table=True):
    """
    原始归档表
    仅作为原始文件（PDF/Word）解析后的文本归档
    """
    __tablename__ = "documents"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户
    # 索引优化：按用户查询用户的文档列表
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # 文档类型枚举
    # 确定文档的处理方式和解析逻辑
    type: DocumentType = Field(nullable=False)

    # 巨型文本存储区
    # 存储解析后的纯文本内容，方便全文检索
    content: str = Field(nullable=False)
