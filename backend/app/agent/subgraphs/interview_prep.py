"""
面试准备子图

该子图封装了面试准备的完整流程：
1. 上下文剪枝：从数据库检索相关资产和面试经验
2. [TODO] 生成器：生成针对性的面试准备建议（问题预测、回答要点）

此子图可以在主图中作为一个整体节点使用。
"""

from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.sharednodes.pruner import pruner_node

# TODO: 待 generator_node 实现后启用
# from app.agent.sharednodes.generator import generator_node


def create_interview_prep_subgraph() -> StateGraph:
    """
    创建面试准备子图

    工作流:
        pruner_node -> [TODO] generator_node -> END

    当前简化版本:
        pruner_node -> END

    Returns:
        编译后的子图实例
    """
    # 创建子图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("pruner_node", pruner_node)
    # TODO: 待实现后添加
    # workflow.add_node("generator_node", generator_node)

    # 设置入口点
    workflow.set_entry_point("pruner_node")

    # 添加边：线性流程
    # TODO: 待实现后启用
    # workflow.add_edge("pruner_node", "generator_node")
    # workflow.add_edge("generator_node", END)

    # 当前简化流程
    workflow.add_edge("pruner_node", END)

    # 编译子图
    return workflow.compile()


# 创建全局子图实例（可选）
interview_prep_subgraph = create_interview_prep_subgraph()
