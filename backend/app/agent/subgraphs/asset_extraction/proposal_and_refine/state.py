"""
Proposal & Refine 子图状态定义

该状态用于资产提案的生成、展示、用户反馈和保存流程。
"""

from typing import Annotated, List, TypedDict, Optional

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class ProposalAndRefineState(TypedDict, total=False):
    """
    Proposal & Refine 子图状态

    包含以下核心功能区域：
    1. 提案生成与展示
    2. 用户反馈收集
    3. 提案调整与保存
    """

    # --- 对话历史 ---
    messages: Annotated[List[BaseMessage], add_messages]

    # --- 待确认的提案列表 ---
    # 作用：存储从 L1 观察中生成的待确认提案
    # 格式：List[AssetProposal] (来自 app.agent.models)
    pending_proposals: Optional[List[dict]]

    # --- 用户反馈 ---
    # 作用：记录用户对提案的反馈（接受/拒绝/修改建议）
    # 格式：{"proposal_id": "accept/reject/modify", "feedback": "用户意见"}
    user_feedback: Optional[dict]

    # --- 当前处理状态 ---
    # 作用：记录当前处于哪个阶段（生成/展示/确认/保存）
    current_stage: Optional[str]

    # --- 已保存的资产 ---
    # 作用：记录本次会话中用户确认并保存到 L2 的资产
    saved_assets: Optional[List[dict]]
