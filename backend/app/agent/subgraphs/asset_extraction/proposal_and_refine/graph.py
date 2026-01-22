"""
Proposal & Refine 子图定义 (人生说明书编辑器)

该子图负责资产提案的生成、展示、用户反馈和保存流程：

    graph TD
        START((Start)) --> LOADER[EditorLoader<br/>查 DB, 填 State]
        LOADER --> PROPOSER[Proposer]
        PROPOSER --> SCHEDULER{Scheduler<br/>Index < Len?}

        SCHEDULER -->|Yes| HUMAN[Human<br/>Interrupt]
        HUMAN --> ROUTER{Router<br/>用户意图?}

        ROUTER -->|修改| REFINER[Refiner]
        REFINER --> HUMAN

        ROUTER -->|放弃| SKIPPER[Skipper]
        SKIPPER --> SCHEDULER

        ROUTER -->|确认| SAVER[SingleSaver]
        SAVER --> SCHEDULER

        SCHEDULER -->|No| END((End))

    工作流程（游标循环机制）：
    1. EditorLoader: 从 DB 加载 pending 状态的 L1 观察，填入 State
    2. Proposer: 批量生成 3-5 条草稿，设置 active_index=0
    3. Scheduler: 检查 active_index < len(current_drafts)
    4. Human: 展示 current_drafts[active_index]，等待用户反馈
    5. Router: 根据用户意图路由（修改/确认/跳过）
    6. Refiner: 修改当前草稿（可选），返回 Human
    7. Skipper: 跳过当前草稿，active_index += 1，返回 Scheduler
    8. SingleSaver: 保存当前草稿，active_index += 1，返回 Scheduler
"""

from langgraph.graph import StateGraph, END

from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import EditorState
from app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes import (
    editor_loader_node,
    proposer_node,
    human_node,
    refiner_node,
    skipper_node,
    single_saver_node,
    route_scheduler,
    route_after_saver,
    route_user_intent,
)


def create_proposal_and_refine_subgraph() -> StateGraph:
    """
    创建 Proposal & Refine 子图（游标循环架构）

    工作流程:
        editor_loader_node -> proposer_node -> route_scheduler (条件边)
            -> human_node (interrupt) -> route_user_intent (条件边)
            -> refiner_node -> human_node (循环)
            -> single_saver_node -> route_scheduler (循环)
            -> route_scheduler -> END

    游标循环机制:
    1. Proposer 批量生成 current_drafts（如 3-5 条）
    2. active_index 游标指示当前处理位置 (0, 1, 2...)
    3. 循环: draft[active_index] -> 用户反馈 -> 修改/存档 -> active_index += 1
    4. 直到 active_index >= len(current_drafts) 结束

    Returns:
        编译后的子图实例，配置了 interrupt_after['human_node']
        (human_node 执行完后中断，用户能看到草稿)
    """
    # 创建子图
    workflow = StateGraph(EditorState)

    # 添加节点
    workflow.add_node("editor_loader_node", editor_loader_node)
    workflow.add_node("proposer_node", proposer_node)
    workflow.add_node("human_node", human_node)
    workflow.add_node("refiner_node", refiner_node)
    workflow.add_node("skipper_node", skipper_node)
    workflow.add_node("single_saver_node", single_saver_node)

    # 设置入口点：从 editor_loader_node 开始
    workflow.set_entry_point("editor_loader_node")

    # 添加边：loader -> proposer
    workflow.add_edge("editor_loader_node", "proposer_node")

    # 添加条件边：proposer -> scheduler (决定是否进入循环)
    workflow.add_conditional_edges(
        "proposer_node",
        route_scheduler,
        {
            "human_node": "human_node",
            "__end__": END,
        }
    )

    # 添加条件边：human -> router (根据用户反馈决定下一步)
    workflow.add_conditional_edges(
        "human_node",
        route_user_intent,
        {
            "refiner_node": "refiner_node",
            "skipper_node": "skipper_node",
            "single_saver_node": "single_saver_node",
        }
    )

    # 添加边：refiner -> human (循环返回，继续修改)
    workflow.add_edge("refiner_node", "human_node")

    # 添加条件边：skipper -> scheduler (跳过后检查是否还有下一条)
    workflow.add_conditional_edges(
        "skipper_node",
        route_scheduler,
        {
            "human_node": "human_node",
            "__end__": END,
        }
    )

    # 添加边：single_saver -> after_saver (保存后检查错误并决定下一步)
    workflow.add_conditional_edges(
        "single_saver_node",
        route_after_saver,
        {
            "human_node": "human_node",
            "__end__": END,
        }
    )

    # 编译子图：使用节点级中断（interrupt() 函数）
    # 不再使用 interrupt_before，而是由 human_node 内部的 interrupt() 函数控制暂停
    # 这样可以完美支持嵌套子图中的数据透传
    compiled_graph = workflow.compile()
    return compiled_graph


# 创建全局子图实例（可选）
proposal_and_refine_subgraph = create_proposal_and_refine_subgraph()
