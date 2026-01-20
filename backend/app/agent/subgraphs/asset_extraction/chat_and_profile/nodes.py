"""
Chat & Profile 子图节点 (T2-01.2)

该子图负责：
1. ChatBot: 与用户进行自然对话，引导分享职业信息
2. ProfileLoader: 从 L1 数据库加载用户观察摘要
3. Profiler: 静默监听对话，挖掘用户的技能、特质、经历片段、偏好
4. Router: 决定继续聊天还是进入 proposal_and_refine 子图

支持多轮对话累积信息，当信息量足够时触发整理阶段。
"""

from typing import Optional

from langgraph.graph.state import RunnableConfig
from langchain_core.messages import BaseMessage, AIMessage, SystemMessage

from app.agent.llm_factory import get_llm
from app.agent.models import ProfilerOutput
from app.agent.sharednodes.user_utils import get_or_create_user
from app.agent.subgraphs.asset_extraction.utils import save_observation_to_l1, get_existing_observations_summary
from app.agent.subgraphs.asset_extraction.prompts import (
    CHATBOT_SYSTEM_PROMPT_TEMPLATE,
    CHATBOT_WELCOME_MESSAGE,
    CHATBOT_FALLBACK_MESSAGE,
    EMPTY_USER_PROFILE_SNAPSHOT,
    PROFILER_SYSTEM_PROMPT,
    PROFILER_SYSTEM_PROMPT_WITH_PROFILE,
)
from app.agent.subgraphs.asset_extraction.chat_and_profile.state import ChatAndProfileState


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


# =============================================================================
# LangGraph 节点定义
# =============================================================================

def profile_loader_node(state: ChatAndProfileState, config: RunnableConfig) -> ChatAndProfileState:
    """
    ProfileLoader 节点：从 L1 数据库加载用户观察摘要到 State

    功能：
    1. 从 config 中获取 username（支持多用户）
    2. 查询 L1 数据库获取用户所有观察记录
    3. 如果用户不存在，自动创建新用户
    4. 将观察摘要写入 state.l1_observations_summary

    设计原则：
    - 只在会话开始时调用一次，本轮对话内复用
    - L1 包含所有历史观察（包括未整理的泥沙）
    - 用于 ChatBot 了解用户背景，Profiler 做增量去重

    Args:
        state: 当前对话状态（此节点不依赖 state，仅保留签名兼容性）
        config: LangGraph 运行配置，需包含 config["configurable"]["username"]

    Returns:
        ChatAndProfileState: 更新后的状态，包含 l1_observations_summary
    """
    print("--- 进入 ProfileLoader 节点 ---")

    # 1. 从 config 解析 username
    username = _get_username_from_config(config)
    print(f"[ProfileLoader] 加载用户观察摘要: {username}")

    # 2. 获取或创建用户
    user = get_or_create_user(username)
    print(f"[ProfileLoader] 用户 ID: {user.id}")

    # 3. 读取 L1 观察摘要（只读一次，本轮对话复用）
    l1_summary, has_existing = get_existing_observations_summary(user.id, max_per_category=50)

    if not has_existing:
        print(f"[ProfileLoader] 用户暂无历史观察，使用默认提示")
        l1_summary = EMPTY_USER_PROFILE_SNAPSHOT
    else:
        print(f"[ProfileLoader] 已加载 {l1_summary.count(chr(10))} 行观察摘要")

    # 4. 返回 L1 摘要到 state（供 chat_node 和 profiler_node 复用）
    return {
        "l1_observations_summary": l1_summary
    }


def chat_node(state: ChatAndProfileState, _config: RunnableConfig) -> ChatAndProfileState:
    """
    ChatBot 节点：负责跟用户愉快的聊天，除此之外什么也不干

    核心职责：
    1. 以职业教练身份与用户进行自然对话
    2. 基于 L1 观察摘要提供个性化回应
    3. 引导用户分享职业相关信息
    4. 不做资产提取、不做提案生成（由 Profiler 负责）

    Args:
        state: 包含 messages 和 l1_observations_summary 的当前状态
        _config: LangGraph 运行配置（此节点不依赖 config，保留签名兼容性）

    Returns:
        ChatAndProfileState: 更新后的状态，包含新的 AI 回复消息
    """
    print("--- 进入 ChatBot 节点 ---")

    # 1. 获取对话历史
    messages = state.get("messages", [])

    # 2. 获取最新用户消息（缓存到 state 供 profiler_node 使用）
    latest_user_message = None
    for msg in reversed(messages):
        if msg.type == "human":
            latest_user_message = msg
            break

    # 3. 获取 L1 观察摘要（如果不存在，使用默认空提示）
    l1_summary = state.get("l1_observations_summary", "")
    if not l1_summary:
        l1_summary = EMPTY_USER_PROFILE_SNAPSHOT

    # 4. 处理空消息情况：发送欢迎语
    if not messages:
        # 如果没有历史消息，发送欢迎语（使用提示词常量）
        # LangGraph 的 add_messages reducer 会自动生成 ID
        return {
            "messages": [AIMessage(content=CHATBOT_WELCOME_MESSAGE)],
            "last_user_message": None
        }

    # 5. 构建对话上下文：System Prompt（包含 L1 观察摘要）
    system_prompt = CHATBOT_SYSTEM_PROMPT_TEMPLATE.format(
        user_profile_snapshot=l1_summary
    )

    # 6. 调用 LLM 生成回应
    try:
        llm = get_llm()

        # 构建消息列表：System Prompt + 历史对话
        # LangGraph 的 add_messages reducer 确保 messages 是 List[BaseMessage]
        # 直接使用即可，无需额外转换
        lc_messages = [SystemMessage(content=system_prompt)] + messages

        # 调用 LLM（流式输出在调用层处理，节点只负责状态更新）
        response = llm.invoke(lc_messages)

        # 7. 返回更新后的状态（添加 AI 回复到消息列表 + 缓存用户消息）
        # LangGraph 的 add_messages reducer 会自动生成 ID
        return {
            "messages": [response],  # 直接使用 LLM 返回的 response
            "last_user_message": latest_user_message
        }

    except Exception as e:
        # LLM 调用失败时的降级处理（使用提示词常量）
        print(f"[ChatBot Error] LLM 调用失败: {str(e)}")

        # LangGraph 的 add_messages reducer 会自动生成 ID
        return {
            "messages": [AIMessage(content=CHATBOT_FALLBACK_MESSAGE)],
            "last_user_message": latest_user_message
        }


def profiler_node(state: ChatAndProfileState, config: RunnableConfig) -> ChatAndProfileState:
    """
    Profiler 节点：侧写师，后台默默分析对话，挖掘用户的闪光点和潜能

    核心职责：
    1. 静默监听对话（用户无感知）
    2. 从对话中提取用户的技能、特质、经历片段、偏好
    3. 增量去重：基于缓存的 L1 摘要，只保存新信息或补充细节
    4. 高召回率：宁可错杀不可放过，捕捉一切可能的线索
    5. 直接写入 L1（raw_observations）表，无需用户确认

    设计原则：
    - 这是"内循环"的一部分，每轮对话后自动运行
    - 追求高召回率，不追求高精确度（精确度由用户确认环节保证）
    - 充分挖掘用户的特质和潜能，不只关注职业
    - L1 是泥沙层，可以碎片化，保留细节
    - 增量去重：使用 profile_loader_node 预加载的 L1 摘要（避免重复查库）

    Args:
        state: 包含 messages 和 l1_observations_summary 的当前对话状态
        config: LangGraph 运行配置，包含 username

    Returns:
        ChatAndProfileState: 更新后的状态，包含 last_turn_analysis
    """
    print("--- 进入 Profiler 节点 ---")

    # 1. 从 state 获取缓存的最新用户消息（由 chat_node 缓存）
    latest_user_message = state.get("last_user_message")

    if not latest_user_message:
        print("[Profiler] 未找到用户消息，跳过分析")
        return {"last_turn_analysis": None}

    # 2. 获取对话历史（用于统计和日志）
    messages = state.get("messages", [])

    # 3. 获取 user_id（使用通用工具函数）
    username = _get_username_from_config(config)
    user = get_or_create_user(username)
    user_id = user.id

    # 4. 从 state 读取 L1 观察摘要（profile_loader_node 已加载，避免重复查库）
    existing_summary = state.get("l1_observations_summary", "")
    has_existing_info = bool(existing_summary) and existing_summary != EMPTY_USER_PROFILE_SNAPSHOT

    # 调试：打印 L1 摘要信息
    print(f"[Profiler Debug] 用户 ID: {user_id}")
    print(f"[Profiler Debug] 是否有历史观察: {has_existing_info}")
    if has_existing_info:
        summary_lines = existing_summary.count('\n')
        print(f"[Profiler Debug] L1 摘要行数: {summary_lines}")
        print(f"[Profiler Debug] L1 摘要预览（前 500 字符）:\n{existing_summary[:500]}...")

    # 5. 选择合适的 System Prompt（如果有已有信息，使用带去重逻辑的 Prompt）
    if has_existing_info:
        system_prompt = PROFILER_SYSTEM_PROMPT_WITH_PROFILE.format(
            existing_observations_summary=existing_summary
        )
        print(f"[Profiler Debug] 使用带去重的 Prompt (PROFILER_SYSTEM_PROMPT_WITH_PROFILE)")
    else:
        system_prompt = PROFILER_SYSTEM_PROMPT
        print(f"[Profiler Debug] 使用基础 Prompt (PROFILER_SYSTEM_PROMPT)")

    # 6. 调用 LLM 进行结构化分析
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(ProfilerOutput)

        # 构建消息列表：System Prompt（含已有信息） + 缓存的最新用户消息
        # 使用 chat_node 缓存的用户消息，而不是 messages[-1]（后者可能是 AI 回复）
        lc_messages = [SystemMessage(content=system_prompt), latest_user_message]

        # 调试：打印最新用户消息
        print(f"[Profiler Debug] 用户消息类型: {latest_user_message.type}")
        print(f"[Profiler Debug] 用户消息内容（前 200 字符）:\n{str(latest_user_message.content)[:200]}...")

        # 调用 LLM
        result = structured_llm.invoke(lc_messages)

        # 调试：打印 LLM 输出
        print(f"[Profiler Debug] LLM 分析摘要: {result.analysis_summary}")
        print(f"[Profiler Debug] LLM 提取的观察数量: {len(result.observations)}")
        print(f"[Profiler Debug] LLM 识别的重复数量: {len(result.duplicates_found)}")

        # 7. 批量写入 L1 数据库（LLM 已做语义去重，无需节点去重）
        observations_saved = []
        observations_skipped = []  # LLM 识别为重复的内容

        if result.observations:
            for i, obs in enumerate(result.observations):
                # 调试：打印每条观察
                print(f"[Profiler Debug] 观察 #{i+1}: [{obs.category.value}] {obs.fact_content[:100]}... (置信度: {obs.confidence}, 潜力: {obs.is_potential_signal})")

                # 获取来源消息的 UUID（用于血缘追踪）
                source_msg_uuid = latest_user_message.id if hasattr(latest_user_message, 'id') else None
                if source_msg_uuid:
                    print(f"[Profiler Debug] 来源消息 UUID: {source_msg_uuid}")
                else:
                    print(f"[Profiler Debug] 警告：来源消息无 UUID，血缘追踪将缺失")

                # LLM 已经做了语义去重，直接保存
                success = save_observation_to_l1(
                    user_id=user_id,
                    category=obs.category,
                    fact_content=obs.fact_content,
                    confidence=obs.confidence,
                    is_potential_signal=obs.is_potential_signal,
                    reasoning=f"[自动提取] {result.analysis_summary}",
                    source_msg_uuid=source_msg_uuid,
                    source_message_count=len(messages),
                    enable_quality_check=True  # 保留质量检查（过滤空话）
                )

                if success:
                    observations_saved.append({
                        "category": obs.category.value,
                        "content": obs.fact_content,
                        "confidence": obs.confidence,
                        "is_potential": obs.is_potential_signal
                    })
                else:
                    print(f"[Profiler Debug] 观察保存失败（可能是质量检查未通过）")

        # 记录 LLM 识别的重复内容
        if result.duplicates_found:
            print(f"[Profiler Debug] LLM 识别的重复内容:")
            for dup in result.duplicates_found:
                print(f"  - {dup}")
                observations_skipped.append({
                    "content": dup,
                    "reason": "llm_identified_duplicate"
                })

        # 统计信息（用于日志，不放入 state）
        total_extracted = len(result.observations)
        total_saved = len(observations_saved)
        total_skipped = len(result.duplicates_found)

        print(f"[Profiler] 提取 {total_extracted} 条新观察，跳过 {total_skipped} 条重复，保存 {total_saved} 条")

        # 累积计数：获取当前会话已累积的观察数量，加上本次新保存的数量
        current_session_count = state.get("session_new_observation_count", 0)
        new_session_count = current_session_count + total_saved

        print(f"[Profiler Debug] 会话累积计数: {current_session_count} -> {new_session_count}")

        # 判断是否应该进入整理阶段
        # 原则1：会话累积的新信息 >= 10 条
        # TODO: 原则2（用户主动意图）需要从对话中检测，暂未实现
        # TODO: 原则3（完整性检测）需要 LLM 判断，暂未实现
        is_ready_to_refine = new_session_count >= 10

        print(f"[Profiler Debug] 是否达到整理阈值: {is_ready_to_refine} (当前: {new_session_count}, 阈值: 10)")

        # 8. 返回分析结果到 state（给 router 看的决策依据）
        return {
            "last_turn_analysis": {
                "has_new_info": total_saved > 0,  # 是否有新信息
                "new_observation_count": total_saved,  # 本次新观察数量
                "is_ready_to_refine": is_ready_to_refine,  # 是否应该进入整理阶段
                "analysis_summary": result.analysis_summary  # 分析摘要（调试用）
            },
            "session_new_observation_count": new_session_count  # 更新累积计数
        }

    except Exception as e:
        # LLM 调用失败，记录错误但不阻断流程
        print(f"[Profiler Error] 分析失败: {str(e)}")
        return {"last_turn_analysis": None}


def chat_router(state: ChatAndProfileState) -> str:
    """
    聊天路由节点：决定继续聊天还是进入整理阶段

    这是 asset_extraction 子图内部的路由逻辑，根据 Profiler 的分析结果
    决定是继续收集信息，还是进入下一步的资产整理阶段。

    Args:
        state: 包含 last_turn_analysis 的当前状态

    Returns:
        str: "continue_chat" | "enter_refinement"
    """
    analysis = state.get("last_turn_analysis")

    if not analysis:
        print("[Router] last_turn_analysis 为空，继续聊天")
        return "continue_chat"

    is_ready = analysis.get("is_ready_to_refine", False)

    if is_ready:
        print(f"[Router] 触发整理阶段（原因：累积信息 >= 10 条）")
        return "enter_refinement"

    print(f"[Router] 继续聊天（未达到整理阈值）")
    return "continue_chat"
