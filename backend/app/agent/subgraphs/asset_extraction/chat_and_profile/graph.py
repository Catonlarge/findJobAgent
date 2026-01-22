"""
Chat & Profile 子图定义

该子图负责与用户的对话交互和隐式资产提取：

    graph TD
        START((Start)) --> LOADER[ProfileLoader]
        LOADER --> CHAT[ChatBot]
        CHAT --> PROFILER[Profiler]
        PROFILER --> END((End))

    工作流程：
    1. ProfileLoader: 加载用户历史观察摘要（使用 checkpoint 恢复状态时，已加载的摘要会被保留）
    2. ChatBot: 与用户对话，引导分享职业信息
    3. Profiler: 静默分析对话，提取新观察并保存到 L1
    4. 子图结束，父图根据 last_turn_analysis 决定下一步

    注意：
    - 每次用户输入都会重新执行这个子图（从 profile_loader 开始）
    - 使用 checkpoint 恢复状态，profile_loader 会检查 state.l1_observations_summary，
      如果已经加载过，可以跳过数据库查询（需要优化）
    - 路由逻辑（决定继续聊天还是进入整理）由父图的 router 处理
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
        profile_loader_node -> chat_node -> profiler_node -> END

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

    # 添加边：loader -> chat
    workflow.add_edge("profile_loader_node", "chat_node")

    # 添加边：chat -> profiler
    workflow.add_edge("chat_node", "profiler_node")

    # 添加边：profiler -> END（父图会根据状态决定下一步）
    workflow.add_edge("profiler_node", END)

    # 编译子图
    return workflow.compile()


# 创建全局子图实例（可选）
chat_and_profile_subgraph = create_chat_and_profile_subgraph()
