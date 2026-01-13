"""
LangGraph 工作流定义 (T2-01.2)

该模块定义了智能求职助手的核心工作流，包括隐性资产提取、
意图路由、上下文剪枝等节点及其连接关系。
"""

from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes.extractor import extractor_node
from app.agent.nodes.router import router_decision_function
from app.agent.nodes.db_ops import save_asset_node, discard_asset_node
from app.agent.nodes.pruner import pruner_node


def create_agent_graph() -> StateGraph:
    """
    创建 Agent 工作流图

    工作流说明：
    1. extractor_node (入口) - 分析用户消息，提取有价值信息
    2. router_decision_function - 决策下一步流向
    3. save_asset_node - 用户确认 (1) 后保存到数据库
    4. discard_asset_node - 用户拒绝 (0) 后丢弃提案
    5. pruner_node - 根据意图剪枝上下文

    Returns:
        编译后的 LangGraph 应用
    """
    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("extractor_node", extractor_node)
    workflow.add_node("save_asset_node", save_asset_node)
    workflow.add_node("discard_asset_node", discard_asset_node)
    workflow.add_node("pruner_node", pruner_node)

    # 设置入口点
    workflow.set_entry_point("extractor_node")

    # 添加边：extractor -> conditional (router)
    # 使用 router_decision_function 作为条件边
    workflow.add_conditional_edges(
        "extractor_node",
        router_decision_function,
        {
            "save_asset_node": "save_asset_node",
            "discard_asset_node": "discard_asset_node",
            "extractor_node": "extractor_node",
            "pruner_node": "pruner_node",
            "onboarding_node": END  # 待实现
        }
    )

    # 添加边：save/discard -> extractor (循环回提取器)
    workflow.add_edge("save_asset_node", "extractor_node")
    workflow.add_edge("discard_asset_node", "extractor_node")

    # 添加边：pruner -> END (待扩展到 generator)
    workflow.add_edge("pruner_node", END)

    # 编译图
    app = workflow.compile()
    return app


# 创建全局图实例
agent_graph = create_agent_graph()
