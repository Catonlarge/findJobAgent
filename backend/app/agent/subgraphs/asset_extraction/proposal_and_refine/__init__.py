"""
Proposal & Refine 子图模块

该子图负责资产提案的生成、展示、用户反馈和保存流程。

使用示例:
    from app.agent.subgraphs.asset_extraction.proposal_and_refine import create_proposal_and_refine_subgraph

    # 在主图中添加子图
    subgraph = create_proposal_and_refine_subgraph()
    workflow.add_node("proposal_and_refine", subgraph)
"""

from app.agent.subgraphs.asset_extraction.proposal_and_refine.graph import (
    create_proposal_and_refine_subgraph,
    proposal_and_refine_subgraph,
)
from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import ProposalAndRefineState
from app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes import (
    proposal_generator_node,
    proposal_presenter_node,
    proposal_refiner_node,
    asset_saver_node,
    feedback_router,
)

__all__ = [
    "create_proposal_and_refine_subgraph",
    "proposal_and_refine_subgraph",
    "ProposalAndRefineState",
    "proposal_generator_node",
    "proposal_presenter_node",
    "proposal_refiner_node",
    "asset_saver_node",
    "feedback_router",
]
