"""
Agent 数据模型 - LLM 结构化输出模式

该模块定义了 Agent 节点与 LLM 交互时使用的结构化输出模式，
确保 LLM 返回的数据符合预期格式。
"""

from pydantic import BaseModel, Field
from app.models.profile import ProfileSectionKey


class AssetProposal(BaseModel):
    """
    资产提案模型 - LLM 结构化输出模式

    该模型定义了 LLM 从用户输入中提取有价值职业信息后
    必须返回的结构化数据，用于生成待确认的提案。

    用途：
    - 连接 LLM 输出与 State 暂存区
    - 确保提取的信息符合数据库字段约束
    - 通过 is_empty 字段可以表示空提案（无资产检测）

    设计说明：
    - 当 is_empty=True 时，表示未检测到有价值信息
    - 当 is_empty=False 时，其他字段才有意义
    """
    is_empty: bool = Field(
        default=False,
        description="是否为空提案：True 表示未检测到有价值的职业信息，False 表示成功提取资产"
    )
    section_key: ProfileSectionKey = Field(
        default="career_potential",
        description="必须从指定的枚举值 (skills, work_experience, project_details, behavioral_traits, career_potential) 中选择最匹配的一项。仅在 is_empty=False 时有效"
    )
    refined_content: str = Field(
        default="",
        description="转化后的内容：第一人称，保留个性细节，去除口语废话。例如：'我掌握 Python 和 FastAPI，曾用它们构建过 RESTful API'。仅在 is_empty=False 时有效"
    )
    thought: str = Field(
        default="",
        description="[调试用] 推理过程：解释为什么提取这段话，保留了哪些细节。例如：'用户明确提到技术栈，属于硬技能'。仅在 is_empty=False 时有效"
    )
    chatMessage: str = Field(
        default="",
        description="给用户对话内容 了解了上一段对话之后，继续跟用户的对话内容"
    )


class EmptyProposal(BaseModel):
    """
    空提案模型 - 无资产检测时的返回值

    当 LLM 判断用户输入不包含有价值的职业信息时返回，
    避免生成无效提案。
    """
    is_empty: bool = Field(
        default=True,
        description="标记为空提案，表示未检测到有价值的职业信息"
    )
