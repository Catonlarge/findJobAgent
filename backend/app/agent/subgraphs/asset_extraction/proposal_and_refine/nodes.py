"""
Proposal & Refine 子图节点 (T2-01.2 续)

该子图负责：
1. EditorLoader: 从数据库加载 L1 观察记录（只查 pending 状态）
2. Proposer: 从 L1 观察中批量生成档案草稿
3. Scheduler Edge: 检查 active_index < len(current_drafts)
4. Human: 展示草稿给用户，收集反馈（通过 interrupt 实现）
5. Router Edge: 根据用户意图路由（修改/确认/跳过）
6. Refiner: 单条精修当前草稿
7. SingleSaver: 即时保存当前草稿到 L2，翻转 L1 状态，active_index += 1

架构：游标循环机制 - 批量提案 -> 单件精修 -> 即时存档
"""

from typing import List, Literal
from langgraph.graph.state import RunnableConfig
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from sqlmodel import Session, select

from app.agent.subgraphs.asset_extraction.utils import format_current_draft_for_display

from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import (
    EditorState,
    ObservationSchema,
    ProfileItemSchema,
    ProposerOutput,
)
from app.agent.llm_factory import get_llm
from app.agent.prompts import (
    PROPOSER_SYSTEM_PROMPT,
    PROPOSER_USER_PROMPT_TEMPLATE,
    REFINER_SYSTEM_PROMPT,
    REFINER_USER_PROMPT_TEMPLATE,
)
from app.agent.sharednodes.user_utils import get_or_create_user
from app.db.init_db import get_engine
from app.models.observation import RawObservation, ObservationStatus
from app.models.profile import ProfileSection, ProfileSectionKey


# =============================================================================
# 辅助函数
# =============================================================================

def _get_username_from_config(config: RunnableConfig) -> str:
    """
    从 LangGraph config 中获取 username

    Args:
        config: LangGraph 的 RunnableConfig

    Returns:
        str: 用户名，默认 'me'

    Raises:
        ValueError: 如果 config 格式不正确
    """
    configurable = config.get("configurable", {})
    username = configurable.get("username", "me")

    if not isinstance(username, str):
        raise ValueError(f"username must be a string, got {type(username).__name__}")

    return username

def _map_section_name_to_key(section_name: str) -> ProfileSectionKey:
    """
    将 section_name 映射到 ProfileSectionKey 枚举

    Args:
        section_name: 中文名称，如 "技能", "经历", "特质", "偏好"

    Returns:
        ProfileSectionKey: 对应的枚举值
    """
    mapping = {
        "技能": ProfileSectionKey.SKILLS,
        "经历": ProfileSectionKey.WORK_EXPERIENCE,
        "特质": ProfileSectionKey.BEHAVIORAL_TRAITS,
        "偏好": ProfileSectionKey.CAREER_POTENTIAL,
    }
    return mapping.get(section_name, ProfileSectionKey.CAREER_POTENTIAL)


def _format_observations_for_proposer(raw_materials: List[ObservationSchema]) -> str:
    """格式化 L1 观察列表为 Proposer Prompt"""
    if not raw_materials:
        return "【暂无观察记录】"

    lines = []
    for i, obs in enumerate(raw_materials, 1):
        obs_id = getattr(obs, "id", "N/A")
        category = getattr(obs, "category", "unknown")
        fact = getattr(obs, "fact_content", "")
        confidence = getattr(obs, "confidence", 0)
        is_signal = getattr(obs, "is_potential_signal", False)

        signal_mark = " [潜力信号]" if is_signal else ""
        lines.append(
            f"{i}. [ID:{obs_id}] {category}{signal_mark} (置信度:{confidence}/100)\n"
            f"   内容: {fact}"
        )

    return "\n".join(lines)


# =============================================================================
# LangGraph 节点定义
# =============================================================================

def editor_loader_node(state: EditorState, config: RunnableConfig) -> EditorState:
    """
    EditorLoader 节点：从数据库加载 L1 观察记录（只查 pending 状态）

    这是实现"滚动更新"的第一步：只加载新的未消费素材。
    """
    print("--- 进入 EditorLoader 节点，正在进货... ---")

    # 使用 username 解析获取 user_id（与 chat_and_profile 子图保持一致）
    username = _get_username_from_config(config)
    user = get_or_create_user(username)
    user_id = user.id

    print(f"[EditorLoader] 加载用户观察: username={username}, user_id={user_id}")

    with Session(get_engine()) as session:
        statement = select(RawObservation).where(
            RawObservation.user_id == user_id,
            RawObservation.status == ObservationStatus.PENDING
        ).order_by(RawObservation.created_at)
        results = session.exec(statement).all()

    raw_materials: List[ObservationSchema] = []
    for obs in results:
        raw_materials.append(ObservationSchema(
            id=obs.id,
            fact_content=obs.fact_content,
            category=obs.category.value,
            source_msg_uuid=obs.source_msg_uuid,
            confidence=obs.confidence,
            is_potential_signal=obs.is_potential_signal
        ))

    print(f"[EditorLoader] 捞到了 {len(raw_materials)} 条 pending 状态的 L1 观察")

    return {
        "raw_materials": raw_materials,
        "current_drafts": [],
        "active_index": 0,
        "messages": []
    }


def proposer_node(state: EditorState, config: RunnableConfig) -> EditorState:
    """
    Proposer 节点：批量提案者

    核心职责：
    1. 读取用户的 L1 原始观察 (raw_materials)
    2. 使用 LLM 将观察聚类、去重、整理成 3-5 条职业化草稿
    3. 初始化游标循环：设置 active_index=0
    """
    print("--- 进入 Proposer 节点 ---")

    raw_materials: List[ObservationSchema] = state.get("raw_materials", [])

    if not raw_materials:
        print("[Proposer] 没有原材料，生成空草稿列表")
        return {
            "current_drafts": [],
            "active_index": 0,
            "messages": [AIMessage(content="暂无可整理的观察记录，请先进行对话收集信息。")]
        }

    print(f"[Proposer] 收到 {len(raw_materials)} 条 L1 观察，开始生成草稿...")

    try:
        llm = get_llm()
        observations_formatted = _format_observations_for_proposer(raw_materials)
        user_prompt = PROPOSER_USER_PROMPT_TEMPLATE.format(
            observations_formatted=observations_formatted
        )

        structured_llm = llm.with_structured_output(ProposerOutput)
        messages = [
            SystemMessage(content=PROPOSER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]

        result: ProposerOutput = structured_llm.invoke(messages)
        current_drafts: List[ProfileItemSchema] = result.drafts

        print(f"[Proposer] 成功生成 {len(current_drafts)} 条草稿")
        if result.analysis_summary:
            print(f"[Proposer] 分析摘要: {result.analysis_summary}")

        return {
            "current_drafts": current_drafts,
            "active_index": 0,
            "messages": []
        }

    except Exception as e:
        print(f"[Proposer Error] LLM 调用失败: {str(e)}")
        return {
            "current_drafts": [],
            "active_index": 0,
            "messages": [AIMessage(content=f"生成草稿时出错：{str(e)}，请稍后重试。")]
        }


def human_node(state: EditorState, config: RunnableConfig) -> EditorState:
    """
    Human 节点：人机交互断点

    核心职责：
    1. 展示 current_drafts[active_index] 给用户
    2. 等待用户输入（通过 LangGraph interrupt 机制）
    3. 用户输入后通过 messages 传给 Router

    注意：这个节点本身不返回任何状态变更，只作为断点。
    前端需要读取 state["current_drafts"][state["active_index"]] 并展示。
    """
    idx = state.get("active_index", 0)
    drafts = state.get("current_drafts", [])

    if idx >= len(drafts):
        print(f"[Human] 索引 {idx} 超出范围，应该结束")
        return state

    current_draft = drafts[idx]
    print(f"[Human] 展示第 {idx + 1}/{len(drafts)} 条草稿: {current_draft.section_name}")

    # 展示当前草稿供用户审阅
    print(format_current_draft_for_display(drafts, idx))

    # 提示用户操作
    print("请审阅以上草稿：")
    print("  - 输入修改意见（如：'把Python改成Java'）")
    print("  - 或输入 '确认' / 'confirm' 保存本条")
    print("  - 或输入 '跳过' / 'skip' 跳过本条")

    # 这个节点配置为 interrupt_after，执行完后会暂停
    # 返回 state 不变，等待用户输入后继续
    return state


def route_scheduler(state: EditorState) -> Literal["human_node", "__end__"]:
    """
    Scheduler 边：检查是否还有草稿需要处理

    判断逻辑：
    - active_index < len(current_drafts) -> human_node (继续处理)
    - active_index >= len(current_drafts) -> __end__ (结束)
    """
    idx = state.get("active_index", 0)
    drafts = state.get("current_drafts", [])

    print(f"[Scheduler] 检查: active_index={idx}, len(drafts)={len(drafts)}")

    if idx < len(drafts):
        return "human_node"
    else:
        print("[Scheduler] 所有草稿已处理完毕，结束")
        return "__end__"


def route_user_intent(state: EditorState) -> Literal["refiner_node", "single_saver_node"]:
    """
    Router 边：根据用户反馈决定下一步

    判断逻辑：
    - 用户输入包含 "确认"/"通过"/"ok"/"1" -> single_saver_node (保存)
    - 其他 -> refiner_node (修改)
    """
    messages = state.get("messages", [])
    if not messages:
        print("[Router] 没有用户消息，默认返回 refiner")
        return "refiner_node"

    last_msg = messages[-1]
    content = last_msg.content.lower() if hasattr(last_msg.content, "lower") else last_msg.content

    # 确认关键词
    confirm_keywords = ["确认", "通过", "ok", "好的", "1", "yes", "save"]
    if any(keyword in content for keyword in confirm_keywords):
        print(f"[Router] 用户确认，进入 SingleSaver")
        return "single_saver_node"
    else:
        print(f"[Router] 用户要求修改，进入 Refiner")
        return "refiner_node"


def refiner_node(state: EditorState, config: RunnableConfig) -> EditorState:
    """
    Refiner 节点：单条精修者

    核心职责：
    1. 锁定 current_drafts[active_index]
    2. 获取用户的修改意见（从 messages[-1]）
    3. 使用 LLM 修改当前草稿
    4. 原地更新 current_drafts[active_index]
    """
    print("--- 进入 Refiner 节点 ---")

    idx = state.get("active_index", 0)
    drafts = state.get("current_drafts", [])

    if idx >= len(drafts):
        print("[Refiner] 索引超出范围")
        return state

    current_draft = drafts[idx]
    messages = state.get("messages", [])

    if not messages:
        print("[Refiner] 没有用户修改意见")
        return state

    user_instruction = messages[-1].content
    print(f"[Refiner] 修改第 {idx + 1} 条草稿，用户意见: {user_instruction}")

    try:
        llm = get_llm()
        user_prompt = REFINER_USER_PROMPT_TEMPLATE.format(
            section_name=current_draft.section_name,
            standard_content=current_draft.standard_content,
            tags=", ".join(current_draft.tags),
            user_instruction=user_instruction
        )

        # 使用结构化输出，复用 ProfileItemSchema
        structured_llm = llm.with_structured_output(ProfileItemSchema)
        messages_llm = [
            SystemMessage(content=REFINER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]

        refined_draft: ProfileItemSchema = structured_llm.invoke(messages_llm)

        # 原地更新
        drafts[idx] = ProfileItemSchema(
            standard_content=refined_draft.standard_content,
            tags=refined_draft.tags,
            source_l1_ids=current_draft.source_l1_ids,  # 保持不变
            section_name=refined_draft.section_name
        )

        print(f"[Refiner] 修改完成")

        # 注意：不更新 active_index，不清空 messages，方便继续多轮对话
        return {
            "current_drafts": drafts
        }

    except Exception as e:
        print(f"[Refiner Error] LLM 调用失败: {str(e)}")
        # 失败时不修改草稿
        return state


def single_saver_node(state: EditorState, config: RunnableConfig) -> EditorState:
    """
    SingleSaver 节点：即时存档员

    核心职责：
    1. 锁定 current_drafts[active_index]
    2. 写入 L2 profile_sections 表
    3. 核销对应的 L1 观察（状态翻转为 promoted）
    4. active_index += 1，清空 messages

    这是实现"滚动更新"的第二步：用掉的被踢出。
    """
    print("--- 进入 SingleSaver 节点 ---")

    idx = state.get("active_index", 0)
    drafts = state.get("current_drafts", [])

    if idx >= len(drafts):
        print("[SingleSaver] 索引超出范围")
        return state

    draft = drafts[idx]

    # 使用 username 解析获取 user_id（与 chat_and_profile 子图保持一致）
    username = _get_username_from_config(config)
    user = get_or_create_user(username)
    user_id = user.id

    print(f"[SingleSaver] 保存第 {idx + 1} 条草稿: {draft.section_name} (username={username}, user_id={user_id})")

    try:
        with Session(get_engine()) as session:
            # 1. 写入 L2 profile_sections
            # 注意：这里简化处理，直接写入标准内容
            # 实际可能需要根据 section_name 映射到 ProfileSectionKey
            new_section = ProfileSection(
                user_id=user_id,
                section_key="career_potential",  # 简化处理，实际应动态映射
                content={
                    "standard_content": draft.standard_content,
                    "tags": draft.tags,
                    "section_name": draft.section_name
                }
            )
            session.add(new_section)

            # 2. 核销 L1（状态翻转为 promoted）
            if draft.source_l1_ids:
                statement = select(RawObservation).where(
                    RawObservation.id.in_(draft.source_l1_ids),
                    RawObservation.user_id == user_id
                )
                l1_records = session.exec(statement).all()

                for l1 in l1_records:
                    l1.status = ObservationStatus.PROMOTED

            session.commit()
            print(f"[SingleSaver] 已保存并核销 {len(draft.source_l1_ids)} 条 L1 观察")

    except Exception as e:
        print(f"[SingleSaver Error] 数据库操作失败: {str(e)}")

    # 3. 翻页逻辑
    return {
        "active_index": idx + 1,
        "messages": []  # 清空对话，为下一条做准备
    }
