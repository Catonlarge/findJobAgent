"""
Proposal & Refine 子图定义

该子图负责资产提案的生成、展示、用户反馈和保存流程：

    graph TD
        START((Start)) --> GENERATOR[ProposalGenerator]
        GENERATOR --> PRESENTER[ProposalPresenter]

        PRESENTER --> ROUTER{FeedbackRouter}

        ROUTER -->|accept| SAVER[AssetSaver]
        ROUTER -->|modify| REFINER[ProposalRefiner]
        ROUTER -->|reject| END((End))

        REFINER --> PRESENTER
        SAVER --> END

    工作流程：
    1. ProposalGenerator: 从 L1 观察中生成待确认提案
    2. ProposalPresenter: 展示提案，收集用户反馈
    3. FeedbackRouter: 根据反馈决定下一步
    4. ProposalRefiner: 调整提案（可选）
    5. AssetSaver: 保存用户接受的提案到 L2
"""

from langgraph.graph import StateGraph, END

from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import ProposalAndRefineState
from app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes import (
    proposal_generator_node,
    proposal_presenter_node,
    proposal_refiner_node,
    asset_saver_node,
    feedback_router,
)


def create_proposal_and_refine_subgraph() -> StateGraph:
    """
    创建 Proposal & Refine 子图

    工作流程:
        proposal_generator_node -> proposal_presenter_node -> feedback_router (条件边)
            -> save_assets: asset_saver_node -> END
            -> refine_proposals: proposal_refiner_node -> proposal_presenter_node
            -> back_to_chat: END（返回 chat_and_profile 子图）

    Returns:
        编译后的子图实例
    """
    # 创建子图
    workflow = StateGraph(ProposalAndRefineState)

    # 添加节点
    workflow.add_node("proposal_generator_node", proposal_generator_node)
    workflow.add_node("proposal_presenter_node", proposal_presenter_node)
    workflow.add_node("proposal_refiner_node", proposal_refiner_node)
    workflow.add_node("asset_saver_node", asset_saver_node)

    # 设置入口点
    workflow.set_entry_point("proposal_generator_node")

    # 添加边
    workflow.add_edge("proposal_generator_node", "proposal_presenter_node")

    # 添加条件边：presenter -> router
    workflow.add_conditional_edges(
        "proposal_presenter_node",
        feedback_router,
        {
            "save_assets": "asset_saver_node",
            "refine_proposals": "proposal_refiner_node",
            "back_to_chat": END,
        }
    )

    # 添加边：refiner -> presenter（循环）
    workflow.add_edge("proposal_refiner_node", "proposal_presenter_node")

    # 添加边：saver -> END
    workflow.add_edge("asset_saver_node", END)

    # 编译子图
    return workflow.compile()


# 创建全局子图实例（可选）
proposal_and_refine_subgraph = create_proposal_and_refine_subgraph()
