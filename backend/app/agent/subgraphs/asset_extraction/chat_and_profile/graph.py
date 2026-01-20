"""
Chat & Profile 子图定义

该子图负责与用户的对话交互和隐式资产提取：

    graph TD
        START((Start)) --> LOADER[ProfileLoader]
        LOADER --> CHAT[ChatBot]
        CHAT --> PROFILER[Profiler]
        PROFILER --> END((End))

    工作流程：
    1. ProfileLoader: 加载用户历史观察摘要
    2. ChatBot: 与用户对话，引导分享职业信息
    3. Profiler: 静默分析对话，提取新观察并保存到 L1

    注意：路由逻辑（决定继续聊天或进入 proposal_and_refine）由父图的 router 处理
"""

from langgraph.graph import StateGraph, END

from app.agent.subgraphs.asset_extraction.chat_and_profile.state import ChatAndProfileState
from app.agent.subgraphs.asset_extraction.chat_and_profile.nodes import (
    profile_loader_node,
    chat_node,
    profiler_node,
)


def create_chat_and_profile_subgraph() -> StateGraph:
    """
    创建 Chat & Profile 子图

    工作流程:
        profile_loader_node -> chat_node -> profiler_node -> chat_router (条件边)
            -> continue_chat: 回到 chat_node（继续对话）
            -> enter_refinement: 进入 proposal_and_refine 子图

    Returns:
        编译后的子图实例
    """
    # 创建子图
    workflow = StateGraph(ChatAndProfileState)

    # 添加节点
    workflow.add_node("profile_loader_node", profile_loader_node)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("profiler_node", profiler_node)

    # 设置入口点
    workflow.set_entry_point("profile_loader_node")

    # 添加边
    workflow.add_edge("profile_loader_node", "chat_node")
    workflow.add_edge("chat_node", "profiler_node")

    # 添加边：profiler -> END（路由逻辑由父图的 router 处理）
    workflow.add_edge("profiler_node", END)

    # 编译子图
    return workflow.compile()


# 创建全局子图实例（可选）
chat_and_profile_subgraph = create_chat_and_profile_subgraph()
