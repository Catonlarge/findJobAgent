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
from langgraph.types import interrupt
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

    # 打印进入时的状态
    incoming_messages = state.get("messages", [])
    print(f"[EditorLoader] DEBUG: 进入时 state.messages 数量 = {len(incoming_messages)}")
    if incoming_messages:
        for i, msg in enumerate(incoming_messages[-3:]):  # 打印最后3条消息
            msg_type = msg.type if hasattr(msg, 'type') else type(msg).__name__
            content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else 'N/A'
            print(f"[EditorLoader] DEBUG:   消息 #{i+1} [{msg_type}]: {content_preview}...")

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
    print("--- 进入 Proposer 节点 ---", flush=True)

    raw_materials: List[ObservationSchema] = state.get("raw_materials", [])
    print(f"[Proposer] raw_materials 数量: {len(raw_materials)}", flush=True)

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

        # 【调试】打印每条草稿的 source_l1_ids
        for i, draft in enumerate(current_drafts):
            print(f"[Proposer] 草稿 #{i+1} source_l1_ids: {draft.source_l1_ids} (类型: {type(draft.source_l1_ids)})")

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
    Human 节点：人机交互断点（使用 interrupt() 函数）

    核心职责：
    1. 展示当前草稿给用户（在 interrupt 之前）
    2. 调用 interrupt() 暂停执行，等待用户输入
    3. 接收用户输入（通过 Command(resume=...) 传递）
    4. 将用户输入添加到 state.messages 中

    错误恢复模式：
    - 当 save_error 不为 None 时，显示错误信息而非草稿
    - 用户可以选择：retry(重试) / skip(跳过)

    架构说明：
    - 使用节点级中断（interrupt()），而非系统级中断（interrupt_before）
    - 这样可以在嵌套子图中正确传递数据
    - ChatService 发送 Command(resume={"messages": [...]}) 后
    - interrupt() 会返回这个字典，节点将其返回以更新 State
    """
    print("\n[Human Node] 准备进入审核流程...")

    # 检查是否处于错误恢复模式
    save_error = state.get("save_error")
    idx = state.get("active_index", 0)
    drafts = state.get("current_drafts", [])

    if save_error:
        # 【错误恢复模式】显示错误信息
        print("=" * 50)
        print("[错误恢复模式]")
        print("-" * 20)
        print(f"错误: {save_error.get('error', '未知错误')}")
        print(f"草稿索引: 第 {save_error.get('draft_index', idx) + 1} 条")
        if save_error.get('draft_summary'):
            print(f"草稿摘要: {save_error['draft_summary']}")
        print("=" * 50)
        print("[请输入] retry(重试保存) / skip(跳过本条):")
    else:
        # 【正常审核模式】展示当前草稿
        current_draft = None
        if drafts and idx < len(drafts):
            current_draft = drafts[idx]

        if current_draft:
            print("=" * 50)
            print(f"[待审核草稿] (第 {idx + 1}/{len(drafts)} 条)")
            print("-" * 20)
            print(f"[分类]: {current_draft.section_name}")
            print(f"[内容]: {current_draft.standard_content}")
            if current_draft.tags:
                print(f"[标签]: {', '.join(current_draft.tags)}")
            print("=" * 50)
            print("[请输入您的修改建议]（或者输入 '确认' / 'confirm' 保存本条）:")
        else:
            print("[警告] 当前没有找到有效的草稿，但程序暂停于此。")

    # 【暂停阶段】挂起等待指令
    # 程序运行到这里会完全停止
    # value 参数的内容可以在 LangGraph Studio 或 checkpointer 里看到
    print(f"[Human Node] DEBUG: 准备调用 interrupt()...")
    print(f"[Human Node] DEBUG: 当前 state.messages 数量 = {len(state.get('messages', []))}")
    if state.get('messages'):
        for i, msg in enumerate(state.get('messages', [])[-3:]):  # 打印最后3条消息
            msg_type = msg.type if hasattr(msg, 'type') else type(msg).__name__
            content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else 'N/A'
            print(f"[Human Node] DEBUG:   消息 #{i+1} [{msg_type}]: {content_preview}...")

    user_feedback_payload = interrupt(value={
        "task": "error_recovery" if save_error else "review",
        "draft_index": idx,
        "save_error": save_error
    })

    # --- [这里是时间静止线，直到 ChatService 发送 Command] ---

    # 【恢复阶段】处理接收到的数据
    # user_feedback_payload 就是 ChatService 发送过来的 {"messages": [HumanMessage(...)]}
    print(f"[Human Node] 收到指令，继续运行...")
    print(f"[Human Node] DEBUG: 收到的 payload 类型 = {type(user_feedback_payload)}")
    print(f"[Human Node] DEBUG: payload 值 = {user_feedback_payload}")
    if isinstance(user_feedback_payload, dict):
        print(f"[Human Node] DEBUG: payload keys = {user_feedback_payload.keys()}")
        if "messages" in user_feedback_payload:
            print(f"[Human Node] DEBUG: messages 数量 = {len(user_feedback_payload['messages'])}")
            if user_feedback_payload["messages"]:
                last_msg = user_feedback_payload["messages"][-1]
                print(f"[Human Node] DEBUG: 最后一条消息类型 = {type(last_msg).__name__}")
                print(f"[Human Node] DEBUG: 最后一条消息内容 = '{last_msg.content}'")

    # 【更新 State】
    # 直接返回接收到的 payload，LangGraph 会自动将其合并到 EditorState 中
    # 因为 payload 结构是 {"messages": [...]}，符合 State 定义
    if isinstance(user_feedback_payload, dict):
        return user_feedback_payload

    return {}


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
        print("\n" + "=" * 50)
        print("所有草稿已审核完成并保存")
        print("您可以继续与 AI 对话，系统会根据新的对话内容更新您的人生说明书")
        print("=" * 50 + "\n")
        return "__end__"


def route_after_saver(state: EditorState) -> Literal["human_node", "__end__"]:
    """
    SingleSaver 后的路由：根据是否有错误决定去向

    判断逻辑：
    - save_error 不为 None -> human_node (错误恢复模式)
    - save_error 为 None -> route_scheduler (正常流程)
    """
    save_error = state.get("save_error")

    if save_error:
        print(f"[AfterSaver] 检测到保存错误，返回 human_node 进行错误恢复")
        return "human_node"
    else:
        # 没有错误，使用正常的 scheduler 路由
        return route_scheduler(state)


def route_user_intent(state: EditorState) -> Literal["refiner_node", "skipper_node", "single_saver_node"]:
    """
    Router 边：根据用户反馈决定下一步

    判断逻辑：
    - 如果处于错误恢复模式 (save_error 不为 None):
      - "retry" -> single_saver_node (重试保存)
      - "skip" -> skipper_node (跳过)
    - 正常审核模式:
      - 用户输入包含 "确认"/"通过"/"ok" -> single_saver_node (保存)
      - 用户输入包含 "放弃"/"skip" -> skipper_node (跳过)
      - 其他 -> refiner_node (修改)
    """
    messages = state.get("messages", [])
    save_error = state.get("save_error")
    print(f"[Router] DEBUG: ========== route_user_intent 开始 ==========")
    print(f"[Router] DEBUG: messages 数量 = {len(messages)}, save_error={save_error is not None}")

    if not messages:
        # 没有用户消息，默认返回 refiner（防御性编程）
        print("[Router] DEBUG: 没有用户消息，默认返回 refiner")
        print(f"[Router] DEBUG: ========== route_user_intent 结束 ==========")
        return "refiner_node"

    last_msg = messages[-1]
    print(f"[Router] DEBUG: 最后一条消息类型 = {type(last_msg).__name__}")
    print(f"[Router] DEBUG: 最后一条消息 type 属性 = {last_msg.type if hasattr(last_msg, 'type') else 'N/A'}")

    content = last_msg.content.lower() if hasattr(last_msg.content, "lower") else last_msg.content
    content_preview = str(content)[:100] if content else 'Empty'
    print(f"[Router] DEBUG: 最后一条消息内容（前100字符） = '{content_preview}'")

    # 【错误恢复模式路由】
    if save_error:
        retry_keywords = ["retry", "重试"]
        if any(keyword in content for keyword in retry_keywords):
            print("[Router] 错误恢复模式：用户选择重试，进入 SingleSaver")
            print(f"[Router] DEBUG: ========== route_user_intent 结束 ==========")
            return "single_saver_node"
        else:
            print("[Router] 错误恢复模式：用户选择跳过，进入 Skipper")
            print(f"[Router] DEBUG: ========== route_user_intent 结束 ==========")
            return "skipper_node"

    # 【正常审核模式路由】
    # 精确匹配指令：用户只输入指定命令时才触发
    content_trimmed = content.strip()

    # 跳过指令：只输入 "skip"
    if content_trimmed == "skip":
        print("[Router] 用户放弃本条草稿，进入 Skipper")
        print(f"[Router] DEBUG: ========== route_user_intent 结束 ==========")
        return "skipper_node"

    # 确认指令：只输入 "ok" 或 "确认"
    if content_trimmed in ("ok", "确认"):
        print("[Router] 用户确认，进入 SingleSaver")
        print(f"[Router] DEBUG: ========== route_user_intent 结束 ==========")
        return "single_saver_node"

    # 默认为修改意图
    print("[Router] 用户要求修改，进入 Refiner")
    print(f"[Router] DEBUG: ========== route_user_intent 结束 ==========")
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

    print(f"[Refiner] DEBUG: active_index = {idx}, drafts 数量 = {len(drafts)}")

    if idx >= len(drafts):
        print("[Refiner] 索引超出范围")
        return state

    current_draft = drafts[idx]
    messages = state.get("messages", [])

    print(f"[Refiner] DEBUG: messages 数量 = {len(messages)}")

    if not messages:
        print("[Refiner] 没有用户修改意见")
        return state

    user_instruction = messages[-1].content
    instruction_preview = str(user_instruction)[:100] if user_instruction else 'Empty'
    print(f"[Refiner] 修改第 {idx + 1} 条草稿，用户意见（前100字符）: {instruction_preview}...")

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

        print(f"[Refiner] DEBUG: 开始调用 LLM 修改草稿...")
        refined_draft: ProfileItemSchema = structured_llm.invoke(messages_llm)
        print(f"[Refiner] DEBUG: LLM 返回结果: {refined_draft}")

        # 原地更新
        drafts[idx] = ProfileItemSchema(
            standard_content=refined_draft.standard_content,
            tags=refined_draft.tags,
            source_l1_ids=current_draft.source_l1_ids,  # 保持不变
            section_name=refined_draft.section_name
        )

        print(f"[Refiner] 修改完成")
        print(f"[Refiner] DEBUG: 更新后的草稿内容: {drafts[idx].standard_content[:100]}...")

        # 注意：不更新 active_index，不清空 messages，方便继续多轮对话
        return {
            "current_drafts": drafts
        }

    except Exception as e:
        print(f"[Refiner Error] LLM 调用失败: {str(e)}")
        # 失败时不修改草稿
        return state


def skipper_node(state: EditorState, config: RunnableConfig) -> EditorState:
    """
    Skipper 节点：跳过当前草稿

    核心职责：
    1. 跳过 current_drafts[active_index]，不保存到数据库
    2. active_index += 1
    3. 清空 messages 和 save_error

    适用场景：
    - 正常审核模式：用户输入"放弃"/"skip"
    - 错误恢复模式：保存失败后用户选择跳过

    设计原则：单一职责，只负责跳过逻辑，不耦合保存功能
    """
    print("--- 进入 Skipper 节点 ---")

    idx = state.get("active_index", 0)
    drafts = state.get("current_drafts", [])

    if idx < len(drafts):
        current_draft = drafts[idx]
        print(f"[Skipper] 跳过第 {idx + 1} 条草稿: {current_draft.section_name}")
    else:
        print(f"[Skipper] 索引 {idx} 超出范围，直接前进")

    next_index = idx + 1
    print(f"[Skipper] 前进到索引 {next_index}")

    return {
        "active_index": next_index,
        "save_error": None,  # 清除错误状态（如果存在）
        "messages": []
    }


def single_saver_node(state: EditorState, config: RunnableConfig) -> EditorState:
    """
    SingleSaver 节点：即时存档员

    核心职责：
    1. 锁定 current_drafts[active_index]
    2. 写入 L2 profile_sections 表
    3. 核销对应的 L1 观察（状态翻转为 promoted）
    4. active_index += 1，清空 messages

    设计原则：单一职责，只负责保存逻辑，跳过功能由 Skipper 节点处理

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
            # 根据 section_name 动态映射到 ProfileSectionKey
            section_key = _map_section_name_to_key(draft.section_name)

            # 检查是否已存在相同 section_key 的记录
            from app.models.profile import ProfileSection
            existing_section = session.query(ProfileSection).filter(
                ProfileSection.user_id == user_id,
                ProfileSection.section_key == section_key
            ).first()

            if existing_section:
                # 累积模式：将新草稿追加到 drafts 列表
                if isinstance(existing_section.content, dict):
                    # 确保 drafts 列表存在
                    if "drafts" not in existing_section.content:
                        existing_section.content["drafts"] = []

                    # 追加新草稿
                    existing_section.content["drafts"].append({
                        "standard_content": draft.standard_content,
                        "tags": draft.tags,
                        "section_name": draft.section_name,
                        "source_l1_ids": draft.source_l1_ids
                    })
                    print(f"[SingleSaver] 追加到现有 section_key={section_key}, drafts 数量={len(existing_section.content['drafts'])}")
                else:
                    # 如果 content 不是 dict，重新初始化
                    existing_section.content = {
                        "drafts": [{
                            "standard_content": draft.standard_content,
                            "tags": draft.tags,
                            "section_name": draft.section_name,
                            "source_l1_ids": draft.source_l1_ids
                        }]
                    }
                    print(f"[SingleSaver] 重新初始化 section_key={section_key}")
            else:
                # 如果不存在，创建新记录
                new_section = ProfileSection(
                    user_id=user_id,
                    section_key=section_key,
                    content={
                        "drafts": [{
                            "standard_content": draft.standard_content,
                            "tags": draft.tags,
                            "section_name": draft.section_name,
                            "source_l1_ids": draft.source_l1_ids
                        }]
                    }
                )
                session.add(new_section)
                print(f"[SingleSaver] 创建新 section_key={section_key}")

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

            # 成功：前进索引，清空错误状态，清空消息
            next_index = idx + 1
            return {
                "active_index": next_index,
                "save_error": None,  # 清除错误状态
                "messages": []
            }

    except Exception as e:
        print(f"[SingleSaver Error] 数据库操作失败: {str(e)}")

        # 失败：不前进索引，设置错误状态，返回 human_node 让用户决定
        error_message = f"保存草稿失败（第 {idx + 1} 条）：{str(e)}"
        return {
            "save_error": {
                "error": error_message,
                "draft_index": idx,
                "draft_summary": f"{draft.section_name}: {draft.standard_content[:50]}..."
            },
            "messages": [AIMessage(content=error_message + "\n\n请输入：retry(重试) / skip(跳过)")]
        }
