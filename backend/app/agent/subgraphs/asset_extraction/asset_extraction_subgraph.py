"""
资产提取子图

该子图封装了隐性资产提取的完整流程：
1. 提取器节点分析用户消息
2. 路由决策判断是否有待确认的提案
3. 用户确认后保存，或拒绝后丢弃

此子图可以在主图中作为一个整体节点使用。

这个子图也有自己的结构：

graph TD
    subgraph Main Loop [Main 函数循环]
        INPUT[用户输入]
        PRINT[实时打印 ChatBot 回复]
    end

    subgraph SuperGraph [主图逻辑]
        START((Start)) --> CHAT[ChatBot 子图]
        
        CHAT --> PROFILER[Profiler 节点]
        
        PROFILER --> ROUTER{路由节点}
        
        ROUTER --> |没什么事| END((END))
        ROUTER --> |去整理| EDITOR[Editor 子图]
        
        EDITOR --> END
    end

    %% 关键的数据流向
    INPUT ==> START
    CHAT -.-> |一边生成一边吐字| PRINT
    END ==> INPUT

"""

from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
# TODO: 待完善子图构建逻辑
# from app.agent.subgraphs.asset_extraction.nodes import (
#     profileLoaderNode,
#     chatNode,
#     profilerNode,
#     chatRouter
# )
from app.agent.sharednodes.db_ops import save_asset_node, discard_asset_node










'''
def create_asset_extraction_subgraph() -> StateGraph:
    """
    创建资产提取子图

    工作流:
        extractor_node -> router_decision_function (条件边)
            -> save_asset_node -> END
            -> discard_asset_node -> END
            -> extractor_node (循环: 继续调整)
            -> pruner_node (传递到主图的剪枝节点)

    Returns:
        编译后的子图实例
    """
    # 创建子图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("extractor_node", extractor_node)
    workflow.add_node("save_asset_node", save_asset_node)
    workflow.add_node("discard_asset_node", discard_asset_node)

    # 设置入口点
    workflow.set_entry_point("extractor_node")

    # 添加条件边：extractor -> router
    workflow.add_conditional_edges(
        "extractor_node",
        router_decision_function,
        {
            "save_asset_node": "save_asset_node",
            "discard_asset_node": "discard_asset_node",
            "extractor_node": "extractor_node",
            # 这些路由需要传递给主图
            "pruner_node": END,
            "onboarding_node": END,
        }
    )

    # 添加边：save/discard -> END
    workflow.add_edge("save_asset_node", END)
    workflow.add_edge("discard_asset_node", END)

    # 编译子图
    return workflow.compile()


# 创建全局子图实例（可选）
asset_extraction_subgraph = create_asset_extraction_subgraph()

'''