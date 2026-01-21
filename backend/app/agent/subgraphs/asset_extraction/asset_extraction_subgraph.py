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
from langgraph.graph import StateGraph, END, START, add_messages
from langchain_core.messages import BaseMessage, HumanMessage

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

def entry_point_router(state: AssetExtractionState) -> str:
    """
    父图入口点路由函数

    在每次用户输入时首先执行，检查用户是否请求直接进入编辑器。

    路由逻辑：
    - 用户输入包含 "edit"/"editor"/"整理档案" → proposal_and_refine (直接进入编辑器)
    - 其他 → chat_and_profile (正常聊天流程)

    Args:
        state: 包含 messages 的当前状态

    Returns:
        str: "chat_and_profile" | "proposal_and_refine"
    """
    messages = state.get("messages", [])

    if not messages:
        print("[EntryPointRouter] 没有消息，进入聊天流程")
        return "chat_and_profile"

    # 获取最后一条消息
    last_msg = messages[-1]

    # 只检查用户消息
    if isinstance(last_msg, HumanMessage):
        content = last_msg.content.lower() if hasattr(last_msg.content, "lower") else str(last_msg.content).lower()

        # 检查是否是编辑器命令
        editor_keywords = ["edit", "editor", "整理档案", "整理"]
        if any(keyword in content for keyword in editor_keywords):
            print("[EntryPointRouter] 检测到编辑器命令，直接进入编辑器")
            return "proposal_and_refine"

    print("[EntryPointRouter] 进入聊天流程")
    return "chat_and_profile"




def asset_extraction_router(state: AssetExtractionState) -> str:
    """
    资产提取父图的路由函数

    根据子图执行后的状态，决定下一步流向：
    - 继续聊天 (chat_and_profile)
    - 进入整理阶段 (proposal_and_refine)
    - 结束 (END)

    注意：
    - 使用 checkpoint 恢复状态，profile_loader 只在首次执行
    - 每次用户输入都会启动一轮新的 chat -> profiler 流程

    Args:
        state: 包含 last_turn_analysis 的当前状态

    Returns:
        str: "continue_chat" | "enter_refinement" | "end"
    """
    analysis = state.get("last_turn_analysis")

    if not analysis:
        print("[AssetExtractionRouter] last_turn_analysis 为空，流程结束")
        return "end"

    is_ready = analysis.get("is_ready_to_refine", False)

    if is_ready:
        print(f"[AssetExtractionRouter] 触发整理阶段（原因：累积信息 >= 10 条）")
        return "enter_refinement"

    print(f"[AssetExtractionRouter] 未达到整理阈值，流程结束（等待用户输入）")
    return "end"


# =============================================================================
# 父图创建函数
# =============================================================================

def create_asset_extraction_subgraph(checkpointer=None):
    """
    创建资产提取父图

    该父图编排两个子图的执行流程：
    1. 默认进入 chat_and_profile 子图
    2. chat_and_profile 结束后，根据 router 决定：
       - end: 父图结束（用户可以发送新消息，使用 checkpoint 恢复状态）
       - enter_refinement: 进入 proposal_and_refine
    3. proposal_and_refine 结束后，返回父图 END

    重要：每次用户输入都会调用图，使用 checkpoint 恢复之前的状态。
    这样 profile_loader 只在首次执行，后续轮次会跳过（通过检查 state.l1_observations_summary）

    Args:
        checkpointer: LangGraph checkpointer（可选，用于持久化状态）

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

    # 设置入口点：使用条件边从 START 路由到对应子图
    # 这样可以在入口时就检查用户输入，决定去聊天还是编辑器
    workflow.add_conditional_edges(
        START,
        entry_point_router,
        {
            "chat_and_profile": "chat_and_profile",
            "proposal_and_refine": "proposal_and_refine",
        }
    )

    # 添加条件边：chat_and_profile 结束后的路由
    workflow.add_conditional_edges(
        "chat_and_profile",
        asset_extraction_router,
        {
            "end": END,  # 流程结束（等待用户下一次输入）
            "enter_refinement": "proposal_and_refine",  # 进入整理阶段
        }
    )

    # 添加边：proposal_and_refine 结束后到父图 END
    workflow.add_edge("proposal_and_refine", END)

    # 编译父图（带 checkpointer，如果提供）
    return workflow.compile(checkpointer=checkpointer)
