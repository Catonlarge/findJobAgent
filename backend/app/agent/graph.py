"""
LangGraph 主工作流定义 (T2-01.2)

该模块定义了智能求职助手的核心工作流，包括子图编排和节点连接。

注意：此模块正在迁移到新的子图架构，暂时禁用。
"""

from langgraph.graph import StateGraph, END
from app.agent.state import AgentState

# TODO: 旧架构节点，待迁移到新子图架构
# from app.agent.subgraphs.asset_extraction.nodes import extractor_node
# from app.agent.sharednodes.router import router_decision_function
# from app.agent.sharednodes.db_ops import save_asset_node, discard_asset_node
# from app.agent.sharednodes.pruner import pruner_node


def create_agent_graph() -> StateGraph:
    """
    创建 Agent 工作流图

    注意：旧架构已禁用，等待迁移到新的 chat_and_profile 子图架构

    TODO: 新架构应该是：
        1. 使用 chat_and_profile 子图替代 extractor_node
        2. 使用 proposal_and_refine 子图处理提案确认
        3. 主图 router 根据状态决定调用哪个子图

    旧架构工作流说明（已禁用）：
    1. extractor_node (入口) - 分析用户消息，提取有价值信息
    2. router_decision_function - 决策下一步流向
    3. save_asset_node - 用户确认 (1) 后保存到数据库
    4. discard_asset_node - 用户拒绝 (0) 后丢弃提案
    5. pruner_node - 根据意图剪枝上下文

    Returns:
        编译后的 LangGraph 应用（临时空图）
    """
    # 创建图
    workflow = StateGraph(AgentState)

    # TODO: 添加新架构的子图
    # from app.agent.subgraphs.asset_extraction import (
    #     create_chat_and_profile_subgraph,
    #     create_proposal_and_refine_subgraph,
    #     AssetExtractionState,
    # )
    #
    # chat_subgraph = create_chat_and_profile_subgraph()
    # proposal_subgraph = create_proposal_and_refine_subgraph()
    #
    # workflow.add_node("chat_and_profile", chat_subgraph)
    # workflow.add_node("proposal_and_refine", proposal_subgraph)

    # 旧节点（已禁用）
    # workflow.add_node("extractor_node", extractor_node)
    # workflow.add_node("save_asset_node", save_asset_node)
    # workflow.add_node("discard_asset_node", discard_asset_node)
    # workflow.add_node("pruner_node", pruner_node)

    # TODO: 设置入口点和边（等待新架构）
    # workflow.set_entry_point("chat_and_profile")

    # 临时编译空图
    app = workflow.compile()
    return app


# 创建全局图实例
agent_graph = create_agent_graph()
