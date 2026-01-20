"""
数据库操作节点 (T2-01.2)

该节点负责将用户确认的资产提案写入数据库，或丢弃提案。
"""

from typing import Dict, Any, List, TypedDict, Optional
from sqlmodel import Session
from app.db.init_db import get_engine
from app.repositories.profile_repository import ProfileRepository
from app.models.profile import ProfileSectionKey
from app.agent.prompts import ASSET_SAVED_MSG, ASSET_DISCARDED_MSG


class DBOpsNodeInput(TypedDict, total=False):
    """数据库操作节点的输入结构"""
    pending_proposal: Optional[Dict[str, Any]]
    messages: List[Dict[str, Any]]
    user_id: int


class DBOpsNodeOutput(TypedDict, total=False):
    """数据库操作节点的输出结构"""
    pending_proposal: None
    messages: List[Dict[str, Any]]


def save_asset_node(state: DBOpsNodeInput) -> DBOpsNodeOutput:
    """
    保存资产节点：将用户确认的提案写入数据库

    核心逻辑：
    1. 从 pending_proposal 获取提案
    2. 写入 ProfileSection 表
    3. 清空 pending_proposal
    4. 返回成功消息

    Args:
        state: 包含 pending_proposal、messages 和 user_id 的输入状态

    Returns:
        清空 pending_proposal 并包含成功消息的输出状态
    """
    proposal = state.get("pending_proposal")
    messages = state.get("messages", [])
    user_id = state.get("user_id", 1)

    if not proposal:
        return {"pending_proposal": None, "messages": messages}

    # 1. 解析提案
    section_key_str = proposal.get("section_key")
    content = proposal.get("refined_content")

    try:
        section_key = ProfileSectionKey(section_key_str)
    except ValueError:
        updated_messages = messages.copy()
        updated_messages.append({
            "role": "assistant",
            "content": f"[错误] 无效的 section_key: {section_key_str}"
        })
        return {"pending_proposal": None, "messages": updated_messages}

    # 2. 写入数据库
    with Session(get_engine()) as session:
        repo = ProfileRepository(session)

        # 获取现有内容
        existing_section = repo.get_by_user_and_key(user_id, section_key)

        # 合并内容（JSON 字段可以追加）
        if existing_section and existing_section.content:
            # 如果已存在内容，创建新的条目追加
            existing_content = existing_section.content
            if isinstance(existing_content, dict):
                # 如果是字典，追加新内容
                existing_content.setdefault("extracted_assets", []).append(content)
                new_content = existing_content
            else:
                # 如果是其他类型，包装成列表
                new_content = {"extracted_assets": [existing_content, content]}
        else:
            # 新建内容
            new_content = {"extracted_assets": [content]}

        # 更新数据库
        repo.update_by_user_and_key(
            user_id=user_id,
            section_key=section_key,
            content=new_content
        )

    # 3. 返回成功消息
    updated_messages = messages.copy()
    updated_messages.append({
        "role": "assistant",
        "content": ASSET_SAVED_MSG
    })

    return {
        "pending_proposal": None,
        "messages": updated_messages
    }


def discard_asset_node(state: DBOpsNodeInput) -> DBOpsNodeOutput:
    """
    丢弃资产节点：清空提案并返回放弃消息

    核心逻辑：
    1. 清空 pending_proposal
    2. 返回丢弃消息

    Args:
        state: 包含 messages 的输入状态

    Returns:
        清空 pending_proposal 并包含丢弃消息的输出状态
    """
    messages = state.get("messages", [])

    updated_messages = messages.copy()
    updated_messages.append({
        "role": "assistant",
        "content": ASSET_DISCARDED_MSG
    })

    return {
        "pending_proposal": None,
        "messages": updated_messages
    }
