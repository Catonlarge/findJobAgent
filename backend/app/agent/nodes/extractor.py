"""
隐性资产提取器节点 (T2-01.2)

该节点负责从用户消息中提取有价值的职业信息，并生成待确认的提案。
"""

from typing import Dict, Any, List, TypedDict, Optional, Union
from app.agent.llm_factory import get_llm
from app.agent.prompts import (
    EXTRACTOR_SYSTEM_PROMPT,
    ASSET_CONFIRMATION_TEMPLATE,
    SECTION_DISPLAY_MAP
)
from app.agent.models import AssetProposal, EmptyProposal


class ExtractorNodeInput(TypedDict, total=False):
    """提取器节点的输入结构"""
    messages: List[Dict[str, Any]]
    user_id: int
    pending_proposal: Optional[Dict[str, Any]]


class ExtractorNodeOutput(TypedDict, total=False):
    """提取器节点的输出结构"""
    pending_proposal: Optional[Dict[str, Any]]
    messages: List[Dict[str, Any]]


def extractor_node(state: ExtractorNodeInput) -> ExtractorNodeOutput:
    """
    隐性资产提取器节点

    核心逻辑：
    1. 获取最新用户消息
    2. 调用 LLM 进行结构化提取
    3. 如果有提取结果，生成确认提示
    4. 将提案挂起到 pending_proposal

    设计优势：
    - 非侵入式：无资产时不阻断正常对话
    - 用户主权：必须经 1/0 确认才写入数据库
    - 容错机制：LLM 调用失败时记录错误但不中断流程

    Args:
        state: 包含 messages 和 user_id 的输入状态

    Returns:
        包含 pending_proposal 和 messages 的输出状态
    """
    # 1. 获取最新用户消息
    messages = state.get("messages", [])
    if not messages:
        return {"pending_proposal": None}

    latest_message = messages[-1]
    if latest_message.get("role") != "user":
        return {"pending_proposal": None}

    user_input = latest_message.get("content", "")

    # 2. 调用 LLM 进行结构化提取
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(Union[AssetProposal, EmptyProposal])

        # 构建提示词
        prompt = f"{EXTRACTOR_SYSTEM_PROMPT}\n\n用户输入: {user_input}"

        result = structured_llm.invoke(prompt)

        # 3. 检查是否为空提案
        if isinstance(result, EmptyProposal) or (
            hasattr(result, 'is_empty') and result.is_empty
        ):
            return {"pending_proposal": None}

        # 4. 格式化确认提示
        display_name = SECTION_DISPLAY_MAP.get(
            result.section_key.value,
            result.section_key.value
        )

        bot_msg = ASSET_CONFIRMATION_TEMPLATE.format(
            category_display=display_name,
            content=result.refined_content
        )

        # 5. 返回提案和确认消息
        proposal_dict = {
            "section_key": result.section_key.value,
            "refined_content": result.refined_content,
            "thought": result.thought
        }

        # 复制消息列表避免修改原 state
        updated_messages = messages.copy()
        updated_messages.append({
            "role": "assistant",
            "content": bot_msg
        })

        return {
            "pending_proposal": proposal_dict,
            "messages": updated_messages
        }

    except Exception as e:
        # LLM 调用失败，记录错误但不阻断流程
        print(f"[Extractor Error] {str(e)}")
        return {"pending_proposal": None}
