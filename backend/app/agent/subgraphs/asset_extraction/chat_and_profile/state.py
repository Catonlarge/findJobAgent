"""
Chat & Profile 子图状态定义

该状态是 ChatBot、Profiler 和 Router 共享的上下文。
"""

from typing import Annotated, List, TypedDict, Optional

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class ChatAndProfileState(TypedDict, total=False):
    """
    Chat & Profile 子图状态

    包含以下核心功能区域：
    1. 短期记忆 (Short-term Memory) - 当前对话流
    2. 长期记忆快照 (Long-term Memory Snapshot) - L1 观察摘要
    3. 隐性思维流 (Hidden Thought Stream) - Profiler 分析结果
    4. 会话累积计数器 (Session Accumulator) - 新信息累积量
    5. 最新用户消息缓存 (Latest User Message Cache)
    """

    # --- 1. 短期记忆 (Short-term Memory) ---
    # 作用：记录当前的对话流。
    # 机制：add_messages 是个 reducer，负责把新消息追加到列表末尾。
    messages: Annotated[List[BaseMessage], add_messages]

    # --- 2. 长期记忆快照 (Long-term Memory Snapshot) ---
    # 作用：ChatBot 在开口说话前必须知道"你是谁"，Profiler 需要它做增量去重
    # 来源：在每次对话开始前，从 L1 数据库拉取并渲染成文本
    # 格式示例："技能：Python (入门)\n- 偏好：不喜欢说教"
    # 说明：L1 包含所有历史观察（泥沙层），由 profileLoaderNode 在会话开始时加载一次
    l1_observations_summary: str

    # --- 3. 隐性思维流 (Hidden Thought Stream) ---
    # 作用：Profiler 节点分析完对话后，将决策信息写入这里
    # 用途：给 Router 节点看，决定是否进入 proposal_and_refine 子图进行资产整理
    #
    # 字段含义：
    #   - has_new_info: bool - 是否发现了新信息
    #   - new_observation_count: int - 本次提取到的新观察数量
    #   - is_ready_to_refine: bool - 是否应该进入整理阶段
    #     判断原则（满足任一即触发）：
    #       1. 本轮对话会话累积的新信息 >= 10 条
    #       2. 用户主动表达结束闲聊意图（TODO）
    #       3. 信息已足够形成完整亮点/项目点（TODO）
    #   - analysis_summary: str - 分析摘要（调试用）
    last_turn_analysis: Optional[dict]

    # --- 4. 会话累积计数器 (Session Accumulator) ---
    # 作用：记录当前对话会话中累积提取到的新观察总数
    # 用途：用于判断是否达到进入整理阶段的阈值
    # 说明：每次 profilerNode 成功保存观察时累加，进入整理阶段后重置为 0
    session_new_observation_count: int

    # --- 5. 最新用户消息缓存 (Latest User Message Cache) ---
    # 作用：chatNode 缓存最新用户消息，供 profilerNode 使用
    # 原因：chatNode 和 profilerNode 串行执行，messages[-1] 会取到 AI 回复而非用户输入
    # 说明：chatNode 负责更新此字段，profilerNode 直接读取
    last_user_message: Optional[BaseMessage]
