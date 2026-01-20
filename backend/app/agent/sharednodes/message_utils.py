"""
消息工具函数 - V7.2 UUID 关联支持

提供创建带 UUID 的 LangChain 消息的工具函数。
确保 Profiler 可以正确追踪消息血缘关系。
"""

import uuid
from typing import Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


def create_human_message(
    content: str,
    msg_uuid: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> HumanMessage:
    """
    创建带 UUID 的用户消息

    Args:
        content: 消息内容
        msg_uuid: 消息 UUID（可选，不提供则自动生成）
        metadata: 额外的元数据（可选）

    Returns:
        HumanMessage: 带有 UUID 的 LangChain HumanMessage 对象

    Example:
        >>> msg = create_human_message("你好")
        >>> print(msg.id)  # 自动生成的 UUID
        >>> print(msg.content)  # "你好"

        >>> msg = create_human_message("你好", msg_uuid="custom-uuid-123")
        >>> print(msg.id)  # "custom-uuid-123"
    """
    if msg_uuid is None:
        msg_uuid = str(uuid.uuid4())

    # 合并元数据
    final_metadata = metadata or {}
    final_metadata["created_at"] = final_metadata.get("created_at")

    return HumanMessage(
        content=content,
        id=msg_uuid,
        **({"metadata": final_metadata} if final_metadata else {})
    )


def create_ai_message(
    content: str,
    msg_uuid: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AIMessage:
    """
    创建带 UUID 的 AI 回复消息

    Args:
        content: 消息内容
        msg_uuid: 消息 UUID（可选，不提供则自动生成）
        metadata: 额外的元数据（可选）

    Returns:
        AIMessage: 带有 UUID 的 LangChain AIMessage 对象
    """
    if msg_uuid is None:
        msg_uuid = str(uuid.uuid4())

    final_metadata = metadata or {}
    final_metadata["created_at"] = final_metadata.get("created_at")

    return AIMessage(
        content=content,
        id=msg_uuid,
        **({"metadata": final_metadata} if final_metadata else {})
    )


def create_system_message(
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> SystemMessage:
    """
    创建系统消息（通常不需要 UUID）

    Args:
        content: 消息内容
        metadata: 额外的元数据（可选）

    Returns:
        SystemMessage: LangChain SystemMessage 对象
    """
    return SystemMessage(
        content=content,
        **({"metadata": metadata} if metadata else {})
    )


# ============================================================
# API 调用示例（供参考）
# ============================================================
"""
示例 1: 基本使用
-----------------
from app.agent.sharednodes.message_utils import create_human_message
from langgraph.graph import StateGraph

# 在 API 或 Main Loop 中创建用户消息
user_input = "我会 Python 和 FastAPI"
user_msg = create_human_message(user_input)

# 将消息传递给 LangGraph
# graph.invoke({"messages": [user_msg]}, config)


示例 2: 保留外部 UUID
---------------------
# 如果前端已经生成了 UUID，可以传入
frontend_uuid = "msg-from-frontend-123"
user_msg = create_human_message("你好", msg_uuid=frontend_uuid)


示例 3: 完整的 API 端点示例
-----------------------------
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_uuid: str
    message_uuid: Optional[str] = None  # 前端可以选择提供消息 UUID

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    # 创建带 UUID 的用户消息
    user_msg = create_human_message(
        content=request.message,
        msg_uuid=request.message_uuid  # 如果前端提供了 UUID，使用它
    )

    # 调用 LangGraph
    config = {"configurable": {"thread_id": request.session_uuid}}
    result = await graph.ainvoke(
        {"messages": [user_msg]},
        config=config
    )

    return {"response": result["messages"][-1].content}


示例 4: 批量导入历史消息
-------------------------
# 从数据库加载历史消息时，需要恢复 UUID
def load_messages_from_db(session_id: int):
    engine = get_engine()
    with Session(engine) as session:
        statement = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at)
        messages = session.exec(statement).all()

        lc_messages = []
        for msg in messages:
            if msg.role == MessageRole.USER:
                lc_messages.append(create_human_message(
                    content=msg.content,
                    msg_uuid=msg.msg_uuid  # 恢复数据库中的 UUID
                ))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(create_ai_message(
                    content=msg.content,
                    msg_uuid=msg.msg_uuid  # 恢复数据库中的 UUID
                ))
        return lc_messages
"""
