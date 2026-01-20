"""
资产提取模块父图 (Asset Extraction Parent Graph)

该模块提供两个子图的编排和路由：
1. Chat & Profile: 与用户对话，隐式提取职业信息
2. Proposal & Refine: 生成资产提案，用户确认后保存

架构说明：

    asset_extraction_subgraph (父图)
    │
    ├── chat_and_profile 子图
    │   └── profiler_node (结束) -> 父图 router
    │
    ├── proposal_and_refine 子图
    │   └── (结束或返回) -> 父图 router
    │
    └── asset_extraction_router (父图路由)
        ├── continue_chat: chat_and_profile
        ├── enter_refinement: proposal_and_refine
        └── end: END

使用示例:
    from app.agent.subgraphs.asset_extraction import (
        create_asset_extraction_subgraph,
        AssetExtractionState,
    )

    # 在主图中添加
    workflow.add_node("asset_extraction", create_asset_extraction_subgraph())
"""

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END, add_messages
from langchain_core.messages import BaseMessage

from app.agent.subgraphs.asset_extraction.chat_and_profile import create_chat_and_profile_subgraph
from app.agent.subgraphs.asset_extraction.proposal_and_refine import create_proposal_and_refine_subgraph


# =============================================================================
# 联合状态定义 (Union State)
# =============================================================================

class AssetExtractionState(TypedDict, total=False):
    """
    资产提取模块的联合状态

    这是 chat_and_profile 和 proposal_and_refine 两个子图的共享状态。
    主图使用此状态来确保两个子图之间的数据流转。
    """

    # --- 来自 ChatAndProfileState ---
    messages: Annotated[List[BaseMessage], add_messages]
    l1_observations_summary: str
    last_turn_analysis: dict
    session_new_observation_count: int
    last_user_message: BaseMessage

    # --- 来自 ProposalAndRefineState ---
    pending_proposals: List[dict]
    user_feedback: dict
    current_stage: str
    saved_assets: List[dict]


# =============================================================================
# 导出子图创建函数
# =============================================================================

__all__ = [
    # 父图创建函数
    "create_asset_extraction_subgraph",
    # 子图创建函数（保留向后兼容）
    "create_chat_and_profile_subgraph",
    "create_proposal_and_refine_subgraph",
    # 联合状态
    "AssetExtractionState",
]


# =============================================================================
# 父图路由逻辑
# =============================================================================

def asset_extraction_router(state: AssetExtractionState) -> str:
    """
    资产提取父图的路由函数

    根据子图执行后的状态，决定下一步流向：
    - 继续聊天 (chat_and_profile)
    - 进入整理阶段 (proposal_and_refine)
    - 结束 (END)

    Args:
        state: 包含 last_turn_analysis 的当前状态

    Returns:
        str: "continue_chat" | "enter_refinement" | "end"
    """
    analysis = state.get("last_turn_analysis")

    if not analysis:
        print("[AssetExtractionRouter] last_turn_analysis 为空，继续聊天")
        return "continue_chat"

    is_ready = analysis.get("is_ready_to_refine", False)

    if is_ready:
        print(f"[AssetExtractionRouter] 触发整理阶段（原因：累积信息 >= 10 条）")
        return "enter_refinement"

    print(f"[AssetExtractionRouter] 继续聊天（未达到整理阈值）")
    return "continue_chat"


# =============================================================================
# 父图创建函数
# =============================================================================

def create_asset_extraction_subgraph() -> StateGraph:
    """
    创建资产提取父图

    该父图编排两个子图的执行流程：
    1. 默认进入 chat_and_profile 子图
    2. chat_and_profile 结束后，根据 router 决定：
       - continue_chat: 重新进入 chat_and_profile
       - enter_refinement: 进入 proposal_and_refine
    3. proposal_and_refine 结束后，根据其返回状态决定下一步

    Returns:
        编译后的父图实例
    """
    # 创建父图
    workflow = StateGraph(AssetExtractionState)

    # 编译子图
    chat_subgraph = create_chat_and_profile_subgraph()
    proposal_subgraph = create_proposal_and_refine_subgraph()

    # 添加子图节点
    workflow.add_node("chat_and_profile", chat_subgraph)
    workflow.add_node("proposal_and_refine", proposal_subgraph)

    # 设置入口点：默认从 chat_and_profile 开始
    workflow.set_entry_point("chat_and_profile")

    # 添加条件边：chat_and_profile 结束后的路由
    workflow.add_conditional_edges(
        "chat_and_profile",
        asset_extraction_router,
        {
            "continue_chat": "chat_and_profile",  # 继续聊天
            "enter_refinement": "proposal_and_refine",  # 进入整理阶段
        }
    )

    # 添加边：proposal_and_refine 结束后到父图 END
    # TODO: 将来可能需要根据 proposal_and_refine 的返回状态决定是否回到 chat
    workflow.add_edge("proposal_and_refine", END)

    # 编译父图
    return workflow.compile()
