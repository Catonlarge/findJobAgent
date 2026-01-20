"""
Chat & Profile 子图模块

该子图负责与用户的对话交互和隐式资产提取。

使用示例:
    from app.agent.subgraphs.asset_extraction.chat_and_profile import create_chat_and_profile_subgraph

    # 在主图中添加子图
    subgraph = create_chat_and_profile_subgraph()
    workflow.add_node("chat_and_profile", subgraph)
"""

from app.agent.subgraphs.asset_extraction.chat_and_profile.graph import (
    create_chat_and_profile_subgraph,
    chat_and_profile_subgraph,
)
from app.agent.subgraphs.asset_extraction.chat_and_profile.state import ChatAndProfileState
from app.agent.subgraphs.asset_extraction.chat_and_profile.nodes import (
    profile_loader_node,
    chat_node,
    profiler_node,
    chat_router,
)

__all__ = [
    "create_chat_and_profile_subgraph",
    "chat_and_profile_subgraph",
    "ChatAndProfileState",
    "profile_loader_node",
    "chat_node",
    "profiler_node",
    "chat_router",
]
