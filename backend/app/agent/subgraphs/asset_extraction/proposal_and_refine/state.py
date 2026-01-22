"""
Editor 子图状态定义（人生说明书编辑器）

基于游标循环机制的批量提案->单件精修->即时存档流程。

架构说明：
    Proposer (批量生成) -> Scheduler (条件边) -> Human (人机交互)
        -> Router (意图路由) -> Refiner (修改) / SingleSaver (存档)
        -> 循环直到处理完所有草稿
"""

from typing import Annotated, List, TypedDict, Optional

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


# =============================================================================
# Schema: 数据结构定义
# =============================================================================

class ObservationSchema(BaseModel):
    """
    L1: 原材料 (只读)

    从 raw_observations 表加载的观察记录，用于生成 L2 档案。
    """
    id: int = Field(description="数据库自增 ID")
    fact_content: str = Field(description="观察内容")
    category: str = Field(description="分类：skills/traits/experience/preference")
    source_msg_uuid: Optional[str] = Field(default=None, description="来源消息 UUID，用于血缘追踪")
    confidence: Optional[float] = Field(default=None, description="置信度 0-1")
    is_potential_signal: Optional[bool] = Field(default=None, description="是否为潜能信号")


class ProfileItemSchema(BaseModel):
    """
    L2: 档案草稿 (读写)

    由 LLM 生成的职业化描述，用户确认后存入 profile_sections 表。
    同时用于 LLM 结构化输出（with_structured_output）。
    """
    standard_content: str = Field(
        description="职业化描述：第一人称，去口语化，保留具体细节。例如：'掌握 Python 和 FastAPI 框架，能够独立开发和维护 RESTful API 服务'"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="相关标签列表，如 ['Python', 'FastAPI', '后端开发', 'API设计']"
    )
    source_l1_ids: List[int] = Field(
        default_factory=list,
        description="证据链：关联的 L1 观察 ID 列表，用于血缘追踪"
    )
    section_name: str = Field(
        description="目标分类名称：'技能' / '经历' / '特质' / '偏好'"
    )


class ProposerOutput(BaseModel):
    """
    Proposer 节点 LLM 输出模型

    包装 ProfileItemSchema 列表，用于 with_structured_output。
    """
    drafts: List[ProfileItemSchema] = Field(
        default_factory=list,
        description="生成的 3-5 条档案草稿列表"
    )
    analysis_summary: str = Field(
        default="",
        description="提炼过程的简要分析总结，用于调试和日志"
    )


# =============================================================================
# State: 编辑器状态
# =============================================================================

class EditorState(TypedDict, total=False):
    """
    Editor 子图状态（游标循环模式）

    核心机制：
    1. Proposer 批量生成 current_drafts（如 3-5 条）
    2. active_index 游标指示当前处理位置 (0, 1, 2...)
    3. 循环：展示 draft[active_index] -> 用户反馈 -> 修改/存档 -> active_index += 1
    4. 直到 active_index >= len(current_drafts) 结束

    状态流转：
        START -> Proposer -> Scheduler -> Human -> Router -> Refiner/SingleSaver -> Scheduler
    """

    # --- 1. 对话流 (仅限当前草稿的修改指令) ---
    messages: Annotated[List[BaseMessage], add_messages]

    # --- 2. 原材料 (Input) ---
    # 作用：从 L1 数据库加载的观察记录列表
    # 来源：chat_and_profile 子图结束后，从 raw_observations 表查询
    raw_materials: List[ObservationSchema]

    # --- 3. 工作台 (Work in Progress) ---
    # 作用：LLM 批量生成的档案草稿列表
    # 格式：List[ProfileItemSchema]
    # 生命周期：Proposer 生成 -> Refiner 修改 -> SingleSaver 逐条消费
    current_drafts: List[ProfileItemSchema]

    # --- 4. 游标 (Cursor) ---
    # 作用：指示当前正在处理第几条草稿 (0, 1, 2...)
    # 关键字段：Scheduler 节点通过比较 active_index 和 len(current_drafts) 决定是否继续
    active_index: int

    # --- 5. 错误恢复 (Error Recovery) ---
    # 作用：保存失败时的错误信息，用于 human_node 显示和用户决策
    # 格式：{"error": "错误消息", "draft_index": 3}
    # 生命周期：SingleSaver 失败时设置 -> 用户处理后清除
    save_error: Optional[dict]


