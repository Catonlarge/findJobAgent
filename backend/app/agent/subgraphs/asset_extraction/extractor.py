"""
隐性资产提取器节点 (T2-01.2)

该节点负责从用户消息中提取有价值的职业信息，并生成待确认的提案。
支持用户反馈调整模式。
支持多轮对话累积信息，当信息量足够时生成提案。
这是一个子图
"""

from typing import Annotated, Dict, Any, List, TypedDict, Optional

from langgraph.graph import add_messages
from sqlalchemy import engine
from sqlmodel import false
from app.agent.llm_factory import get_llm
from app.agent.prompts import (
    EXTRACTOR_SYSTEM_PROMPT,
    EXTRACTOR_REFINEMENT_PROMPT,
    ASSET_CONFIRMATION_TEMPLATE,
    ASSET_CONFIRMATION_TEMPLATE_REFINED,
    SECTION_DISPLAY_MAP
)
from app.agent.models import AssetProposal, EmptyProposal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

# 数据库相关
from sqlmodel import Session, select
from app.db.init_db import get_engine
from app.models.user import User
from app.models.profile import ProfileSection


# state定义
class chatState(TypedDict, total=false):
    """
    chat状态: 这是 ChatBot、Profiler 和 Router 共享的上下文。
    """
    # --- 1. 短期记忆 (Short-term Memory) ---
    # 作用：记录当前的对话流。
    # 机制：add_messages 是个 reducer，负责把新消息追加到列表末尾。
    messages: Annotated[List[BaseMessage], add_messages]

    # --- 2. 长期记忆快照 (Long-term Memory Snapshot) ---
    # 作用：这是 V7.2 的灵魂。ChatBot 在开口说话前，必须知道“你是谁”。
    # 来源：在每次对话开始前，从 L2 数据库拉取并渲染成文本。
    # 格式示例："用户画像：\n- 技能：Python (入门)\n- 偏好：不喜欢说教"
    user_profile_snapshot: str

    # --- 3. 隐性思维流 (Hidden Thought Stream) ---
    # 作用：这是给 Profiler (分析员) 看的，ChatBot 其实不需要读它，但需要占个位。
    # ChatBot 说完话后，Profiler 会分析这段话，把结果填在这里。
    last_turn_analysis: Optional[dict]    




# 辅助函数，用来在数据库里面查找用户
# 注意，在测试期间默认本地用户登陆，username = 'me'
def fetch_user_profile_snapshot(username: str = 'me') -> str:
    """
    根据用户名，拉取 L2 档案表 (profile_sections)，
    并将其格式化为适合 System Prompt 的文本快照。

    Args:
        username: 用户名，默认 'me'

    Returns:
        格式化后的用户画像快照文本
    """

    # 1. 准备默认的空状态文案
    # 如果是新用户，LLM 应该看到这个，而不是一片空白
    default_snapshot = (
        "【当前用户画像为空】\n"
        "用户是初次使用，请通过自然的对话（如询问职业背景、技能、目标）"
        "来收集信息，并在适当时候建议'整理档案'。"
    )

    # 2. 获取数据库引擎并创建会话
    engine = get_engine()
    with Session(engine) as session:
        # 3. 查询用户
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()

        if not user:
            return default_snapshot

        # 4. 查询用户的所有画像切片
        profile_statement = select(ProfileSection).where(
            ProfileSection.user_id == user.id
        )
        sections = session.exec(profile_statement).all()

        if not sections:
            return default_snapshot

        # 5. 检查是否有实际内容（过滤空切片）
        sections_with_content = [s for s in sections if s.content]

        if not sections_with_content:
            return default_snapshot

        # 6. 格式化为文本快照
        snapshot_parts = [f"## 用户画像 (用户: {user.username})\n"]

        for section in sections_with_content:
            section_name = section.section_key.value
            snapshot_parts.append(f"### {section_name}")
            snapshot_parts.append(_format_content(section.content))
            snapshot_parts.append("")  # 空行分隔

        return "\n".join(snapshot_parts)


def _format_content(content: Dict[str, Any], indent: int = 0) -> str:
    """
    递归格式化内容为 Markdown

    Args:
        content: 内容字典
        indent: 缩进层级

    Returns:
        格式化后的字符串
    """
    lines = []
    prefix = "  " * indent

    for key, value in content.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_content(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")

    return "\n".join(lines)







# chatNode：负责跟用户愉快的聊天，除此之外什么也不干
def chatNode(state : chatState):
    """
    这是专门负责跟用户聊天的Node
    """








'''
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
    1. 检查是否有 pending_proposal（调整模式）
       - 如果有，使用 EXTRACTOR_REFINEMENT_PROMPT 处理用户反馈
       - 如果无，使用 EXTRACTOR_SYSTEM_PROMPT 提取新资产
    2. 调用 LLM 进行结构化提取/调整
    3. 如果有提取结果，生成确认提示
    4. 将提案挂起到 pending_proposal

    设计优势：
    - 非侵入式：无资产时不阻断正常对话
    - 用户主权：必须经 1/0 确认才写入数据库
    - 反馈循环：支持多轮调整，直到用户满意
    - 容错机制：LLM 调用失败时记录错误但不中断流程

    Args:
        state: 包含 messages、user_id 和 pending_proposal 的输入状态

    Returns:
        包含 pending_proposal 和 messages 的输出状态
    """
    # 1. 获取最新用户消息
    messages = state.get("messages", [])
    latest_message = messages[-1]
    user_input = latest_message.get("content", "")
    pending_proposal = state.get("pending_proposal")
    
    # 复制消息列表避免修改原 state
    # updated_messages = messages.copy()

    # 2. 调用 LLM 进行结构化提取或调整
    try:
        llm = get_llm()
        # 使用单个模型，通过 is_empty 字段判断是否为空提案
        # 这样可以避免 LangChain Union 类型的问题
        structured_llm = llm.with_structured_output(AssetProposal)

        # 判断是调整模式还是新提取模式
        if pending_proposal:
            # 调整模式：用户对现有提案提出反馈
            prompt = EXTRACTOR_REFINEMENT_PROMPT.format(
                previous_section=pending_proposal["section_key"],
                previous_content=pending_proposal["refined_content"],
                user_feedback=user_input
            )
            is_refinement = True
            # 调整模式直接使用文本 prompt
            result = structured_llm.invoke(prompt)
            print(result)
        else:
            # 新提取模式：使用 LangChain 消息格式
            # LLM 可以看到完整的对话历史，包括用户之前说过的所有话
            is_refinement = False

            # 构建消息列表：SystemMessage + 历史对话
            lc_messages = [SystemMessage(content=EXTRACTOR_SYSTEM_PROMPT)]

            # 将字典格式转换为 LangChain 消息格式
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                elif role == "system":
                    lc_messages.append(SystemMessage(content=content))

            # 直接传递消息列表给 LLM
            result = structured_llm.invoke(lc_messages)
            print(result)


        if not result.is_empty:
        # 4. 格式化确认提示（调整模式使用不同模板）
            display_name = SECTION_DISPLAY_MAP.get(
                result.section_key.value,
                result.section_key.value
            )

            if is_refinement:
                bot_msg = ASSET_CONFIRMATION_TEMPLATE_REFINED.format(
                    category_display=display_name,
                    content=result.refined_content
                )
            else:
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

            messages.append({
                "role": "assistant",
                "content": f"{result.chatMessage}"
            })

            # 再添加给用户看的确认消息
            messages.append({
                "role": "assistant",
                "content": bot_msg
            })

            return {
                "pending_proposal": proposal_dict,
                "messages": [f"{result.chatMessage}"]
            }            

        else:
            # 添加AI的回复
            messages.append({
                "role": "assistant",
                "content": f"{result.chatMessage}"
            })

            messages.append({
                "role": "assistant",
                "content": f"{result.thought}"
            })

            return {
                "pending_proposal": None,
                "messages": [f"{result.chatMessage}"]
            }             
            


    except Exception as e:
        # LLM 调用失败，记录错误但不阻断流程
        print(f"[Extractor Error] {str(e)}")
        return {"pending_proposal": None}
'''