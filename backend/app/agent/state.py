"""
LangGraph Agent 状态定义和 ScoredEvaluation 模式
为智能求职助手定义核心状态结构和 LLM 结构化输出模式
"""

from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel, Field

from app.models import ChatIntent


class ScoredEvaluation(BaseModel):
    """
    LLM 结构化输出模式 - 用于 CoT 策略评分

    该模式定义了 LLM 在进行评估和推理时必须返回的结构化数据，
    包含详细的思考过程、评分和改进建议。
    """

    analysis_thought: str = Field(
        description="详细的Chain of Thought分析过程，解释评估的逻辑和推理步骤"
    )

    score: float = Field(
        description="评估得分，范围通常在1-10之间，数值越高表示匹配度越好",
        ge=0.0,
        le=10.0
    )

    evaluation_criteria: List[str] = Field(
        default_factory=list,
        description="评估所依据的具体标准和维度，如技能匹配度、经验相关性等"
    )

    suggestions: List[str] = Field(
        default_factory=list,
        description="基于评估结果给出的具体改进建议和优化方向"
    )

    matches_requirements: bool = Field(
        default=False,
        description="布尔标志，指示是否满足基本要求或达到可接受标准"
    )


class AgentState(TypedDict, total=False):
    """
    LangGraph Agent 状态定义

    该状态贯穿整个 LangGraph 工作流，存储 Agent 处理过程中的所有
    关键信息，包括消息历史、用户画像、评估结果等。
    """

    # 消息历史 - 对话的完整记录
    messages: List[Dict[str, Any]]

    # 剪枝后的上下文字符串 - 包含与当前意图相关的关键信息
    pruned_context_str: str

    # 用户画像数据 - 从数据库加载的用户完整信息
    user_profile: Dict[str, Any]

    # 当前会话意图 - 决定 Router 的走向
    current_intent: ChatIntent

    # 评估结果 - Scorer 节点的结构化输出
    evaluation_result: Optional[ScoredEvaluation]

    # 生成的内容 - Generator 节点输出的简历、求职信等
    generated_artifact: Optional[str]

    # 迭代计数器 - 用于控制循环和防止无限递归，默认为 0
    iteration_count: int

    # 质量检查标志 - 指示生成的内容是否通过质量检验，默认为 False
    quality_check_passed: bool

    # 待确认的资产提案 - T2-01.2 隐性资产提取器
    # 若此字段非空，Router 将优先拦截 "1/0" 指令
    pending_proposal: Optional[Dict[str, Any]]

    # 用户 ID - 用于数据库操作 (从 API 层传递或默认值)
    user_id: int


# AgentState 的默认字段值
DEFAULT_AGENT_STATE = {
    "messages": [],
    "pruned_context_str": "",
    "user_profile": {},
    "current_intent": ChatIntent.GENERAL_CHAT,
    "evaluation_result": None,
    "generated_artifact": None,
    "iteration_count": 0,
    "quality_check_passed": False,
    "pending_proposal": None,
    "user_id": 1
}
