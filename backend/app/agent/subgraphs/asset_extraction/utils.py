"""
资产提取子图的工具函数

提供 asset_extraction 子图内复用的工具函数。
"""

from sqlmodel import Session, select
from app.db.init_db import get_engine
from app.models.observation import RawObservation, ObservationCategory, ObservationStatus
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import ProfileItemSchema


def should_save_observation(
    fact_content: str,
    min_length: int = 5
) -> bool:
    """
    判断观察是否值得保存到 L1

    L1 是高召回层，所以过滤标准非常宽松。
    只过滤明显无价值的内容（过短或为空）。

    注意：不检查置信度，因为 LLM 可能虚报。
    去重逻辑会在另一个函数中处理。

    Args:
        fact_content: 观察内容
        min_length: 内容最短长度（默认 5 个字符）

    Returns:
        bool: True 表示值得保存
    """
    # 基本质量门槛：只过滤空话
    if len(fact_content.strip()) < min_length:
        return False

    return True


def save_observation_to_l1(
    user_id: int,
    category: ObservationCategory,
    fact_content: str,
    confidence: int,
    is_potential_signal: bool,
    reasoning: str,
    source_msg_uuid: Optional[str] = None,
    source_message_count: int = 0,
    enable_quality_check: bool = True
) -> bool:
    """
    保存单条观察到 L1 数据库（泥沙层）

    用于在 asset_extraction 子图内保存观察到 L1 数据库。
    L1 是高召回率的便签本，可以包含碎片化、不确定的信息。

    去重策略：
    - 不在此函数做去重，去重由 LLM 在 profilerNode 中完成（语义级别）
    - 此函数只负责质量检查和持久化

    Args:
        user_id: 用户 ID
        category: 观察分类 (枚举值)
        fact_content: 观察内容，保留用户原话风格和细节
        confidence: 置信度 1-100，明确的陈述 80+，推断的 50-80，微弱信号 30-50
                      （保留用于记录，但不作为过滤条件）
        is_potential_signal: 是否为潜力信号，从平凡小事中发现的潜在闪光点
        reasoning: 为什么认为这条观察有价值
        source_msg_uuid: 来源消息的 UUID（LangChain Message.id），用于血缘追踪
        source_message_count: 来源消息数量（可选，用于追踪）
        enable_quality_check: 是否启用质量检查（默认 True，过滤过短内容）

    Returns:
        bool: 是否保存成功

    Raises:
        Exception: 数据库操作失败时抛出异常
    """
    try:
        # 1. 质量检查（可选）：只过滤空话，不过滤置信度
        if enable_quality_check:
            if not should_save_observation(fact_content):
                print(f"[save_observation_to_l1] 质量检查未通过: content_length={len(fact_content)}")
                return False

        # 2. 创建 RawObservation 记录
        raw_obs = RawObservation(
            user_id=user_id,
            category=category,
            fact_content=fact_content,
            confidence=confidence,
            is_potential_signal=is_potential_signal,
            status=ObservationStatus.PENDING,
            source_msg_uuid=source_msg_uuid,
            context_snapshot={
                "reasoning": reasoning,
                "source_message_count": source_message_count,
                "quality_check_enabled": enable_quality_check
            }
        )

        # 3. 写入数据库
        engine = get_engine()
        with Session(engine) as session:
            session.add(raw_obs)
            session.commit()

        return True

    except Exception as e:
        print(f"[save_observation_to_l1 Error] 保存失败: {str(e)}")
        return False


def save_observation_from_dict(
    user_id: int,
    category: str,
    fact_content: str,
    confidence: int,
    is_potential_signal: bool,
    reasoning: str,
    source_message_count: int = 0
) -> bool:
    """
    保存单条观察到 L1 数据库（从字典参数）

    接受字符串类型的 category，自动转换为枚举。
    主要用于 LLM Tool Calling 场景，LLM 输出的 category 是字符串。

    Args:
        user_id: 用户 ID
        category: 观察分类 (字符串: skill_detect/trait_detect/experience_fragment/preference)
        fact_content: 观察内容
        confidence: 置信度
        is_potential_signal: 是否为潜力信号
        reasoning: 推理说明
        source_message_count: 来源消息数量

    Returns:
        bool: 是否保存成功
    """
    try:
        # 映射 category 字符串到枚举
        category_enum = ObservationCategory(category)

        return save_observation_to_l1(
            user_id=user_id,
            category=category_enum,
            fact_content=fact_content,
            confidence=confidence,
            is_potential_signal=is_potential_signal,
            reasoning=reasoning,
            source_message_count=source_message_count
        )

    except ValueError as e:
        print(f"[save_observation_from_dict Error] 无效的 category: {category}")
        return False
    except Exception as e:
        print(f"[save_observation_from_dict Error] 保存失败: {str(e)}")
        return False


def get_existing_observations_summary(user_id: int, max_per_category: int = 20) -> str:
    """
    获取用户现有观察的摘要，用于增量去重

    从 L1 数据库读取用户已有的观察，按分类汇总成文本，
    供 Profiler 节点注入 Prompt 进行语义级别的增量去重。

    Args:
        user_id: 用户 ID
        max_per_category: 每个分类最多返回多少条观察（避免 Prompt 过长）

    Returns:
        tuple: (formatted_summary: str, has_existing_info: bool)
        - formatted_summary: 格式化的观察摘要文本
        - has_existing_info: 是否有已记录的信息（用于判断使用哪个 Prompt）
    """
    try:
        engine = get_engine()
        with Session(engine) as session:
            # 查询所有观察
            statement = select(RawObservation).where(
                RawObservation.user_id == user_id
            )
            all_obs = session.exec(statement).all()

            if not all_obs:
                return ("【暂无已记录的信息】", False)

            # 按分类整理
            by_category = {
                ObservationCategory.SKILL: [],
                ObservationCategory.TRAIT: [],
                ObservationCategory.EXPERIENCE: [],
                ObservationCategory.PREFERENCE: []
            }

            for obs in all_obs:
                if obs.category in by_category:
                    by_category[obs.category].append(obs.fact_content)

            # 检查是否有实际内容
            total_count = sum(len(contents) for contents in by_category.values())
            if total_count == 0:
                return ("【暂无已记录的信息】", False)

            # 格式化为文本（限制数量）
            summary_parts = []

            for category, contents in by_category.items():
                if contents:
                    # 取最近的 N 条
                    recent_contents = contents[-max_per_category:]
                    category_name = category.value.replace("_", " ").title()
                    summary_parts.append(f"**{category_name}**:")
                    for content in recent_contents:
                        summary_parts.append(f"  - {content}")
                    summary_parts.append("")  # 空行分隔

            return ("\n".join(summary_parts), True)

    except Exception as e:
        print(f"[get_existing_observations_summary Error] 读取失败: {str(e)}")
        return ("【读取已有信息失败，本次对话将不进行增量去重】", False)


def format_draft_for_display(draft: "ProfileItemSchema", index: int, total: int) -> str:
    """
    格式化单条草稿用于控制台展示

    Args:
        draft: 草稿对象 (ProfileItemSchema)
        index: 当前草稿索引 (0-based)
        total: 草稿总数

    Returns:
        str: 格式化后的草稿文本
    """
    separator = "━" * 60
    tags_str = ", ".join(draft.tags) if draft.tags else "无"
    source_ids_str = ", ".join(map(str, draft.source_l1_ids)) if draft.source_l1_ids else "无"

    return f"""
{separator}
【草稿 {index + 1}/{total}】{draft.section_name}
{separator}

{draft.standard_content}

标签: {tags_str}
来源: L1观察ID [{source_ids_str}]
{separator}
"""


def format_current_draft_for_display(
    drafts: List["ProfileItemSchema"],
    active_index: int
) -> str:
    """
    格式化当前待审阅的草稿

    根据 active_index 从 drafts 中提取当前草稿并格式化展示。
    用于在用户交互时显示待审阅的草稿内容。

    Args:
        drafts: 草稿列表 (List[ProfileItemSchema])
        active_index: 当前活跃索引 (0-based)

    Returns:
        str: 格式化后的当前草稿文本，如果索引无效则返回提示信息
    """
    if not drafts:
        return "\n【当前无草稿】\n"

    if active_index < 0 or active_index >= len(drafts):
        return f"\n【索引错误: active_index={active_index}, 草稿总数={len(drafts)}】\n"

    current_draft = drafts[active_index]
    return format_draft_for_display(current_draft, active_index, len(drafts))


def format_all_drafts_summary(drafts: List["ProfileItemSchema"]) -> str:
    """
    格式化所有草稿的摘要信息

    用于快速预览所有生成的草稿，显示每条的标题和简要信息。

    Args:
        drafts: 草稿列表 (List[ProfileItemSchema])

    Returns:
        str: 格式化后的摘要文本
    """
    if not drafts:
        return "\n【无草稿】\n"

    lines = ["\n" + "━" * 60, "【草稿总览】", "━" * 60]

    for idx, draft in enumerate(drafts, 1):
        content_preview = draft.standard_content[:50] + "..." if len(draft.standard_content) > 50 else draft.standard_content
        tags_str = ", ".join(draft.tags[:3]) if draft.tags else "无"
        lines.append(f"{idx}. [{draft.section_name}] {content_preview}")
        lines.append(f"   标签: {tags_str} | 来源: {len(draft.source_l1_ids)} 条观察")
        lines.append("")

    lines.append("━" * 60 + "\n")
    return "\n".join(lines)
