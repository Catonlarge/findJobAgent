"""
意图路由节点 (T2-01.2)

该节点负责根据当前状态决策下一步流向，包括处理资产提取的 1/0 确认逻辑。
"""

from typing import Dict, Any, List, TypedDict, Optional
from app.models.chat import ChatIntent


class RouterNodeInput(TypedDict, total=False):
    """路由节点的输入结构"""
    messages: List[Dict[str, Any]]
    pending_proposal: Optional[Dict[str, Any]]
    current_intent: ChatIntent


class RouterNodeOutput(TypedDict, total=False):
    """路由节点的输出结构（路由决策由函数返回，不直接修改 state）"""
    pass


def router_decision_function(state: RouterNodeInput) -> str:
    """
    路由决策函数：决定下一个节点

    优先级：
    1. 如果有 pending_proposal，检查用户是否输入 1/0
    2. 否则根据 current_intent 路由到其他节点

    路由规则：
    - pending_proposal 存在时：
      - 用户输入 "1" -> save_asset_node
      - 用户输入 "0" -> discard_asset_node
      - 用户输入其他 -> extractor_node (视为放弃当前提案，继续提取)
    - pending_proposal 为空时：
      - resume_refine -> pruner_node
      - interview_prep -> pruner_node
      - onboarding -> onboarding_node (待实现)
      - general_chat -> extractor_node

    Args:
        state: 包含 messages、pending_proposal 和 current_intent 的输入状态

    Returns:
        目标节点名称字符串
    """
    messages = state.get("messages", [])
    proposal = state.get("pending_proposal")

    # 获取最新用户消息
    if messages:
        latest_message = messages[-1]
        if latest_message.get("role") == "user":
            user_input = latest_message.get("content", "").strip()

            # [逻辑分支 1] 处理挂起的提案
            if proposal is not None:
                if user_input == "1":
                    return "save_asset_node"
                elif user_input == "0":
                    return "discard_asset_node"
                # 用户没按 1/0，视为放弃当前提案，继续提取
                return "extractor_node"

    # [逻辑分支 2] 正常意图路由
    current_intent = state.get("current_intent", ChatIntent.GENERAL_CHAT)

    if current_intent == ChatIntent.RESUME_REFINE:
        return "pruner_node"
    elif current_intent == ChatIntent.INTERVIEW_PREP:
        return "pruner_node"
    elif current_intent == ChatIntent.ONBOARDING:
        return "onboarding_node"  # 待实现
    else:
        return "extractor_node"
