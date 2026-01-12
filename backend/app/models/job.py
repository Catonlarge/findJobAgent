"""
资产域模型 - JD 独立表
corresponds to Table 6 in database design document
"""

from typing import Optional, Dict, Any
from sqlmodel import Field, Column, JSON

from .base import TimestampModel

class JobDescription(TimestampModel, table=True):
    """
    JD 独立表
    存储职位描述的独立表，支持 JD 管理列表功能
    """
    __tablename__ = "job_descriptions"

    # 主键
    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键：归属用户，JD 管理列表查询
    # 索引优化：经常按用户查询 JD 列表
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    # 岗位名称
    title: str = Field(nullable=False)

    # 公司名称
    # 可选字段，不是所有 JD 都包含公司信息
    company: Optional[str] = Field(default=None)

    # JD 原始全文
    # 使用 TEXT 类型存储完整的职位描述内容
    raw_content: str = Field(nullable=False)

    # 结构化标签 JSON（可选）
    # AI 解析后提取的关键信息，如技能要求、薪资范围等
    parsed_tags: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
