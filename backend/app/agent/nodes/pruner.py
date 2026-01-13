"""
上下文剪枝器 - 从用户画像中提取与意图相关的关键信息

该模块负责根据当前会话意图（简历优化或面试准备）从用户画像中提取相关字段，
生成精简的上下文字符串，用于后续的LLM推理。
"""

from typing import TypedDict, Dict, Any
from app.models.chat import ChatIntent


class PrunerNodeInput(TypedDict, total=False):
    """剪枝器节点的输入结构"""
    user_profile: Dict[str, Any]
    current_intent: ChatIntent


class PrunerNodeOutput(TypedDict, total=False):
    """剪枝器节点的输出结构"""
    pruned_context_str: str


def pruner_node(state: PrunerNodeInput) -> PrunerNodeOutput:
    """
    上下文剪枝器节点 - 根据意图提取相关用户信息

    核心逻辑：
    - 根据 current_intent 判断当前用户需求
    - 从 user_profile 中提取与意图相关的字段
    - 返回结构化的文本字符串，供后续 LLM 使用

    提升效率的关键：
    - 避免将全部 JSON 输入 LLM，只提供相关信息
    - 减少 token 消耗，提高响应速度
    - 结构化输出便于 LLM 理解和使用

    Args:
        state: 包含 user_profile 和 current_intent 的输入状态

    Returns:
        包含 pruned_context_str 的输出状态
    """
    user_profile = state.get("user_profile", {})
    current_intent = state.get("current_intent", ChatIntent.GENERAL_CHAT)

    # 根据意图选择相关字段
    if current_intent == ChatIntent.RESUME_REFINE:
        relevant_fields = extract_resume_fields(user_profile)
    elif current_intent == ChatIntent.INTERVIEW_PREP:
        relevant_fields = extract_interview_fields(user_profile)
    elif current_intent == ChatIntent.ONBOARDING:
        relevant_fields = extract_onboarding_fields(user_profile)
    else:
        # GENERAL_CHAT - 提取通用信息
        relevant_fields = extract_general_fields(user_profile)

    # 格式化为结构化字符串
    formatted_context = format_context(relevant_fields)

    return {"pruned_context_str": formatted_context}


def extract_resume_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取简历优化相关字段

    关键字段包括：
    - 个人信息（姓名、邮箱、电话、所在地）
    - 教育背景（学校、专业、学位、成绩）
    - 工作经历（公司、职位、时间、职责）
    - 技能列表（技术栈、熟练度）
    - 项目经验（项目名称、描述、技术、成果）
    - 语言能力（语言、水平）

    Args:
        user_profile: 完整的用户画像字典

    Returns:
        仅包含简历相关字段的字典
    """
    # 从基础信息中提取个人信息
    basic_info = user_profile.get("basic_info", {})

    # 从画像切片中提取各个模块（如果可用）
    profile_sections = user_profile.get("profile_sections", [])

    # 构建简历相关字段字典
    resume_fields = {
        "个人信息": {
            "姓名": basic_info.get("姓名") or basic_info.get("name"),
            "邮箱": basic_info.get("邮箱") or basic_info.get("email"),
            "电话": basic_info.get("电话") or basic_info.get("phone"),
            "所在地": basic_info.get("城市") or basic_info.get("location")
        },
        "教育背景": extract_sections_by_key(profile_sections, "education"),
        "工作经历": extract_sections_by_key(profile_sections, "work_experience"),
        "技能专精": extract_sections_by_key(profile_sections, "skills"),
        "项目经验": extract_sections_by_key(profile_sections, "project_details"),
        "语言能力": extract_sections_by_key(profile_sections, "language"),
        "职业概要": extract_sections_by_key(profile_sections, "summary")
    }

    # 过滤掉空值
    return filter_empty_values(resume_fields)


def extract_interview_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取面试准备相关字段

    关键字段包括：
    - 个人信息（姓名、沟通风格）
    - 行为特质（性格特点、价值观）
    - 工作经验（关键成就、职责描述）
    - 项目经验（技术细节、挑战、解决方案）
    - 技能水平（技术栈、实战经验）
    - 求职目标（期望职位、公司类型）

    Args:
        user_profile: 完整的用户画像字典

    Returns:
        仅包含面试相关字段的字典
    """
    basic_info = user_profile.get("basic_info", {})
    profile_sections = user_profile.get("profile_sections", [])

    interview_fields = {
        "个人背景": {
            "姓名": basic_info.get("姓名") or basic_info.get("name"),
            "沟通风格": basic_info.get("沟通风格", "适应性强")
        },
        "行为特质": extract_sections_by_key(profile_sections, "behavioral_traits"),
        "工作经验": extract_sections_by_key(profile_sections, "work_experience"),
        "项目经验": extract_sections_by_key(profile_sections, "project_details"),
        "技能专精": extract_sections_by_key(profile_sections, "skills"),
        "职业目标": {
            "期望职位": basic_info.get("期望职位") or basic_info.get("target_position"),
            "期望行业": basic_info.get("期望行业") or basic_info.get("target_industry"),
            "期望公司": basic_info.get("期望公司") or basic_info.get("target_company")
        }
    }

    return filter_empty_values(interview_fields)


def extract_onboarding_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取引导注册相关字段

    用于引导新用户完善信息，主要关注缺失的关键字段

    Args:
        user_profile: 完整的用户画像字典

    Returns:
        包含当前已有信息的字典，便于识别缺失项
    """
    basic_info = user_profile.get("basic_info", {})
    profile_sections = user_profile.get("profile_sections", [])

    onboarding_fields = {
        "基本信息": {
            key: value
            for key, value in basic_info.items()
            if value  # 只保留非空值
        },
        "现有画像切片": [
            section.get("section_key")
            for section in profile_sections
        ]
    }

    return onboarding_fields


def extract_general_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    提取通用聊天相关字段

    提供基本的用户信息，避免无关细节

    Args:
        user_profile: 完整的用户画像字典

    Returns:
        包含基本信息的字典
    """
    basic_info = user_profile.get("basic_info", {})
    profile_sections = user_profile.get("profile_sections", [])

    general_fields = {
        "个人信息": {
            "姓名": basic_info.get("姓名") or basic_info.get("name"),
            "职业": basic_info.get("职业") or basic_info.get("occupation"),
            "所在地": basic_info.get("城市") or basic_info.get("location")
        },
        "技能概要": extract_sections_by_key(profile_sections, "skills"),
        "职业目标": extract_sections_by_key(profile_sections, "summary")
    }

    return filter_empty_values(general_fields)


def extract_sections_by_key(profile_sections: list, target_key: str) -> Any:
    """
    根据section_key从画像切片列表中提取内容

    Args:
        profile_sections: 画像切片列表
        target_key: 目标section_key

    Returns:
        匹配切片的content字段，如果没有匹配则返回空列表或空字典
    """
    if not profile_sections:
        return []

    result = []
    for section in profile_sections:
        if section.get("section_key") == target_key:
            content = section.get("content", {})
            if isinstance(content, dict):
                result.append(content)
            else:
                result.append(content)

    return result if len(result) > 1 or not result else result[0]


def filter_empty_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    递归过滤字典中的空值（None、空字符串、空列表、空字典）

    Args:
        data: 需要过滤的字典

    Returns:
        过滤后不含空值的字典
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            filtered = filter_empty_values(value)
            if filtered:
                result[key] = filtered
        elif isinstance(value, list):
            filtered = [item for item in value if item not in (None, "", {}, [])]
            if filtered:
                result[key] = filtered
        elif value not in (None, ""):
            result[key] = value

    return result


def format_context(data: Dict[str, Any]) -> str:
    """
    将提取的字段格式化为结构化的文本字符串

    格式说明：
    - 使用markdown风格的标题格式
    - 字段名和值用冒号分隔
    - 列表项用短横线标记
    - 保持层次结构清晰

    Args:
        data: 需要格式化的字段字典

    Returns:
        格式化的文本字符串
    """
    lines = []

    def _format_recursive(obj, level=0, prefix=""):
        """递归格式化字典和列表"""
        indent = "  " * level

        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    if level == 0:
                        lines.append(f"## {key}")
                    else:
                        lines.append(f"{indent}{key}:")
                    _format_recursive(value, level + 1)
                else:
                    lines.append(f"{indent}{key}: {value}")
        elif isinstance(obj, list):
            if obj and isinstance(obj[0], dict):
                # 如果列表元素是字典，逐条列出
                for index, item in enumerate(obj, 1):
                    lines.append(f"{indent}{index}.")
                    _format_recursive(item, level + 1)
            else:
                # 简单列表
                for item in obj:
                    lines.append(f"{indent}- {item}")
        else:
            # 基本类型
            lines.append(f"{indent}{obj}")

    _format_recursive(data)

    return "\n".join(lines)
