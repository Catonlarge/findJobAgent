"""
简历优化子图

该子图封装了简历优化的完整流程：
1. 上下文剪枝：从数据库检索相关资产，构建精简上下文
2. [TODO] 评分器：对简历内容进行质量评分
3. [TODO] 生成器：基于评分和上下文生成优化建议

此子图可以在主图中作为一个整体节点使用。
"""

from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.sharednodes.pruner import pruner_node

# TODO: 待 scorer_node 和 generator_node 实现后启用
# from app.agent.sharednodes.scorer import scorer_node
# from app.agent.sharednodes.generator import generator_node


def create_resume_refine_subgraph() -> StateGraph:
    """
    创建简历优化子图

    工作流:
        pruner_node -> [TODO] scorer_node -> [TODO] generator_node -> END

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
    # workflow.add_node("scorer_node", scorer_node)
    # workflow.add_node("generator_node", generator_node)

    # 设置入口点
    workflow.set_entry_point("pruner_node")

    # 添加边：线性流程
    # TODO: 待实现后启用
    # workflow.add_edge("pruner_node", "scorer_node")
    # workflow.add_edge("scorer_node", "generator_node")
    # workflow.add_edge("generator_node", END)

    # 当前简化流程
    workflow.add_edge("pruner_node", END)

    # 编译子图
    return workflow.compile()


# 创建全局子图实例（可选）
resume_refine_subgraph = create_resume_refine_subgraph()
