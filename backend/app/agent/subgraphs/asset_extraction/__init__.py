"""
资产提取模块

该模块提供两个独立的子图，由主图的 router 来协调调用：
1. Chat & Profile: 与用户对话，隐式提取职业信息
2. Proposal & Refine: 生成资产提案，用户确认后保存

主图使用示例:
    from app.agent.subgraphs.asset_extraction import (
        create_chat_and_profile_subgraph,
        create_proposal_and_refine_subgraph,
        AssetExtractionState,
    )

    # 在主图中添加子图
    chat_subgraph = create_chat_and_profile_subgraph()
    proposal_subgraph = create_proposal_and_refine_subgraph()

    workflow.add_node("chat_and_profile", chat_subgraph)
    workflow.add_node("proposal_and_refine", proposal_subgraph)

    # 主图 router 根据状态决定调用哪个子图
    workflow.add_conditional_edges(
        "main_router",
        route_based_on_state,
        {
            "chat": "chat_and_profile",
            "proposal": "proposal_and_refine",
        }
    )

子图直接导入示例:
    # 单独导入 Chat & Profile 子图
    from app.agent.subgraphs.asset_extraction.chat_and_profile import (
        create_chat_and_profile_subgraph,
        ChatAndProfileState,
    )

    # 单独导入 Proposal & Refine 子图
    from app.agent.subgraphs.asset_extraction.proposal_and_refine import (
        create_proposal_and_refine_subgraph,
        ProposalAndRefineState,
    )
"""

# 从主模块导出
from app.agent.subgraphs.asset_extraction.asset_extraction_subgraph import (
    create_chat_and_profile_subgraph,
    create_proposal_and_refine_subgraph,
    AssetExtractionState,
)

__all__ = [
    # 子图创建函数
    "create_chat_and_profile_subgraph",
    "create_proposal_and_refine_subgraph",
    # 联合状态
    "AssetExtractionState",
]
