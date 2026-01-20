"""
Proposal & Refine 子图节点 (T2-01.2 续)

该子图负责：
1. ProposalGenerator: 从 L1 观察中生成待确认的资产提案
2. ProposalPresenter: 展示提案给用户，收集反馈
3. ProposalRefiner: 根据用户反馈调整提案
4. AssetSaver: 将用户确认的提案保存到 L2 资产库

TODO: 节点实现待完善
"""

from typing import Optional
from langgraph.graph.state import RunnableConfig

from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import ProposalAndRefineState


# =============================================================================
# LangGraph 节点定义 (TODO)
# =============================================================================

def proposal_generator_node(state: ProposalAndRefineState, config: RunnableConfig) -> ProposalAndRefineState:
    """
    ProposalGenerator 节点：从 L1 观察中生成待确认的资产提案

    核心职责：
    1. 读取用户的 L1 原始观察
    2. 将观察聚类、去重、整理成结构化提案
    3. 生成待确认的资产列表

    TODO: 待实现

    Args:
        state: 包含 L1 观察摘要的当前状态
        config: LangGraph 运行配置，包含 username

    Returns:
        ProposalAndRefineState: 更新后的状态，包含 pending_proposals
    """
    print("--- 进入 ProposalGenerator 节点 (TODO) ---")

    # TODO: 实现提案生成逻辑
    return {
        "pending_proposals": [],
        "current_stage": "proposals_generated"
    }


def proposal_presenter_node(state: ProposalAndRefineState, config: RunnableConfig) -> ProposalAndRefineState:
    """
    ProposalPresenter 节点：展示提案给用户，收集反馈

    核心职责：
    1. 将待确认的提案以友好格式展示给用户
    2. 引导用户确认、拒绝或修改提案

    TODO: 待实现

    Args:
        state: 包含 pending_proposals 的当前状态
        config: LangGraph 运行配置

    Returns:
        ProposalAndRefineState: 更新后的状态，包含展示消息
    """
    print("--- 进入 ProposalPresenter 节点 (TODO) ---")

    # TODO: 实现提案展示逻辑
    return {
        "current_stage": "awaiting_feedback"
    }


def proposal_refiner_node(state: ProposalAndRefineState, config: RunnableConfig) -> ProposalAndRefineState:
    """
    ProposalRefiner 节点：根据用户反馈调整提案

    核心职责：
    1. 解析用户的修改意见
    2. 调整提案内容
    3. 重新展示调整后的提案

    TODO: 待实现

    Args:
        state: 包含 user_feedback 的当前状态
        config: LangGraph 运行配置

    Returns:
        ProposalAndRefineState: 更新后的状态，包含调整后的提案
    """
    print("--- 进入 ProposalRefiner 节点 (TODO) ---")

    # TODO: 实现提案调整逻辑
    return {
        "current_stage": "refined"
    }


def asset_saver_node(state: ProposalAndRefineState, config: RunnableConfig) -> ProposalAndRefineState:
    """
    AssetSaver 节点：将用户确认的提案保存到 L2 资产库

    核心职责：
    1. 过滤出用户接受的提案
    2. 批量写入 L2 资产表
    3. 更新用户画像

    TODO: 待实现

    Args:
        state: 包含 user_feedback 的当前状态
        config: LangGraph 运行配置

    Returns:
        ProposalAndRefineState: 更新后的状态，包含 saved_assets
    """
    print("--- 进入 AssetSaver 节点 (TODO) ---")

    # TODO: 实现资产保存逻辑
    return {
        "saved_assets": [],
        "current_stage": "completed"
    }


def feedback_router(state: ProposalAndRefineState) -> str:
    """
    反馈路由节点：根据用户反馈决定下一步

    判断逻辑：
    - 用户接受所有提案 -> asset_saver_node
    - 用户要求修改 -> proposal_refiner_node
    - 用户拒绝提案 -> 返回 chat_and_profile 子图

    TODO: 待实现

    Args:
        state: 包含 user_feedback 的当前状态

    Returns:
        str: "save_assets" | "refine_proposals" | "back_to_chat"
    """
    print("--- 进入 FeedbackRouter 节点 (TODO) ---")

    # TODO: 实现路由逻辑
    return "save_assets"
