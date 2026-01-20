"""
上下文剪枝器 - 从用户画像中提取与意图相关的关键信息

该模块负责根据当前会话意图（简历优化或面试准备）从用户画像中提取相关字段，
生成精简的上下文字符串，用于后续的LLM推理。

设计模式：配置驱动 (Configuration-Driven)
- 业务逻辑与配置分离
- 新增字段只需修改配置常量，无需改动核心代码
"""

from typing import TypedDict, Dict, Any, List
from app.models.chat import ChatIntent


# ============================================================
# 配置常量区域 (Configuration Constants)
# 修改此处即可改变 Agent 的"注意力"
# ============================================================

# 标题映射 - 将数据库字段名翻译为 LLM 易于理解的中文标题
SECTION_TITLES: Dict[str, str] = {
    "basic_info": "基本信息",
    "education": "教育背景",
    "work_experience": "工作经历",
    "projects_summary": "项目摘要",           # 简历用
    "project_details": "项目深度详情 (STAR)", # 面试用
    "skills": "技能列表",
    "behavioral_traits": "性格与软技能",
    "summary": "个人简介"
}


# 意图映射 - 定义不同场景下需要加载哪些字段
#
# 策略说明：
# - resume_refine (改简历): 侧重"广度"和"结果"
# - interview_prep (模拟面试): 侧重"深度"和"特质"
# - onboarding (冷启动): 识别缺失的关键字段
# - default (闲聊/其他): 极简模式

INTENT_MAPPING: Dict[str, List[str]] = {
    "resume_refine": [
        "basic_info",
        "education",
        "work_experience",
        "projects_summary",  # 简历用摘要
        "skills"
        # 剔除: project_details (太长), behavioral_traits (简历不写性格)
    ],
    "interview_prep": [
        "basic_info",
        "project_details",   # 面试用深度详情
        "behavioral_traits",
        "skills"
        # 剔除: projects_summary (信息量不足), education (通常不问细节)
    ],
    "onboarding": [
        "basic_info"
        # 用于识别缺失字段，其他字段动态检查
    ],
    "default": [
        "basic_info",
        "summary"
    ]
}


# ============================================================
# 核心处理逻辑 (Core Processing Logic)
# ============================================================

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
    - 从 INTENT_MAPPING 获取目标字段列表
    - 遍历提取数据，软降级（数据缺失时跳过）
    - 格式化为 Markdown 字符串

    设计优势：
    - 配置驱动：新增字段只需修改 INTENT_MAPPING
    - 无硬编码：纯函数，不包含业务判断
    - 软降级：数据缺失时不报错，自动跳过

    Args:
        state: 包含 user_profile 和 current_intent 的输入状态

    Returns:
        包含 pruned_context_str 的输出状态
    """
    user_profile = state.get("user_profile", {})
    current_intent = state.get("current_intent", ChatIntent.GENERAL_CHAT)

    # 1. 确定要加载的字段列表
    # 将 ChatIntent 枚举转换为字符串键
    intent_key = current_intent.value if hasattr(current_intent, 'value') else str(current_intent)
    if intent_key not in INTENT_MAPPING:
        intent_key = "default"
    target_keys = INTENT_MAPPING.get(intent_key, INTENT_MAPPING["default"])

    # 2. 循环提取数据
    context_parts = []

    for key in target_keys:
        # 2.1 从 user_profile 获取数据
        data = _extract_data_by_key(user_profile, key)

        # 2.2 软降级：数据不存在则跳过
        if data is None or _is_empty(data):
            continue

        # 2.3 获取标题并格式化
        title = SECTION_TITLES.get(key, key)
        formatted_section = _format_section(title, data)
        context_parts.append(formatted_section)

    # 3. 拼接输出
    pruned_context = "\n\n".join(context_parts)

    return {"pruned_context_str": pruned_context}


def _extract_data_by_key(user_profile: Dict[str, Any], key: str) -> Any:
    """
    根据 key 从 user_profile 中提取数据

    数据结构说明：
    - basic_info: 直接从 user_profile["basic_info"] 获取
    - 其他字段: 从 user_profile["profile_sections"] 列表中查找 section_key 匹配的项

    Args:
        user_profile: 完整的用户画像字典
        key: 目标字段名（对应数据库字段名）

    Returns:
        提取的数据，如果不存在则返回 None
    """
    if key == "basic_info":
        return user_profile.get("basic_info")

    # 从 profile_sections 中查找
    profile_sections = user_profile.get("profile_sections", [])
    if not profile_sections:
        return None

    # 查找匹配的 section
    matched_sections = [
        section.get("content", {})
        for section in profile_sections
        if section.get("section_key") == key
    ]

    if not matched_sections:
        return None

    # 如果只有一个匹配，直接返回内容
    # 如果有多个匹配（如多段工作经历），返回列表
    return matched_sections[0] if len(matched_sections) == 1 else matched_sections


def _is_empty(data: Any) -> bool:
    """
    检查数据是否为空

    Args:
        data: 待检查的数据

    Returns:
        True 表示数据为空，False 表示有内容
    """
    if data is None:
        return True
    if isinstance(data, (str, list, dict)) and len(data) == 0:
        return True
    if isinstance(data, dict) and all(v is None or v == "" for v in data.values()):
        return True
    return False


def _format_section(title: str, data: Any) -> str:
    """
    格式化单个数据块为 Markdown

    Args:
        title: 标题（中文）
        data: 数据内容

    Returns:
        格式化后的 Markdown 字符串
    """
    lines = [f"## {title}", ""]

    def _format_recursive(obj, level=0):
        """递归格式化字典和列表"""
        indent = "  " * level

        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{indent}{key}:")
                    _format_recursive(value, level + 1)
                else:
                    lines.append(f"{indent}{key}: {value}")
        elif isinstance(obj, list):
            if obj and isinstance(obj[0], dict):
                # 列表元素是字典，逐条列出
                for index, item in enumerate(obj, 1):
                    lines.append(f"{indent}{index}.")
                    _format_recursive(item, level + 1)
            else:
                # 简单列表
                for item in obj:
                    lines.append(f"{indent}- {item}")

    _format_recursive(data)
    lines.append("")
    return "\n".join(lines)


# ============================================================
# 向后兼容函数 (Backward Compatibility)
# 为了保持现有测试通过，保留旧函数的接口
# ============================================================

def extract_resume_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """向后兼容：提取简历优化相关字段（已废弃，使用 pruner_node）"""
    state = {"user_profile": user_profile, "current_intent": ChatIntent.RESUME_REFINE}
    result = pruner_node(state)
    return _parse_context_to_dict(result.get("pruned_context_str", ""))


def extract_interview_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """向后兼容：提取面试准备相关字段（已废弃，使用 pruner_node）"""
    state = {"user_profile": user_profile, "current_intent": ChatIntent.INTERVIEW_PREP}
    result = pruner_node(state)
    return _parse_context_to_dict(result.get("pruned_context_str", ""))


def extract_onboarding_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """向后兼容：提取引导注册相关字段（已废弃，使用 pruner_node）"""
    basic_info = user_profile.get("basic_info", {})
    profile_sections = user_profile.get("profile_sections", [])

    return {
        "基本信息": {k: v for k, v in basic_info.items() if v},
        "现有画像切片": [
            section.get("section_key")
            for section in profile_sections
        ]
    }


def extract_general_fields(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """向后兼容：提取通用聊天相关字段（已废弃，使用 pruner_node）"""
    state = {"user_profile": user_profile, "current_intent": ChatIntent.GENERAL_CHAT}
    result = pruner_node(state)
    return _parse_context_to_dict(result.get("pruned_context_str", ""))


def extract_sections_by_key(profile_sections: list, target_key: str) -> Any:
    """
    向后兼容：根据 section_key 从画像切片列表中提取内容
    （已废弃，使用 _extract_data_by_key）
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
    向后兼容：递归过滤字典中的空值
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
    向后兼容：将提取的字段格式化为结构化的文本字符串
    （已废弃，使用 _format_section）
    """
    lines = []

    def _format_recursive(obj, level=0, prefix=""):
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
                for index, item in enumerate(obj, 1):
                    lines.append(f"{indent}{index}.")
                    _format_recursive(item, level + 1)
            else:
                for item in obj:
                    lines.append(f"{indent}- {item}")
        else:
            lines.append(f"{indent}{obj}")

    _format_recursive(data)
    return "\n".join(lines)


def _parse_context_to_dict(context_str: str) -> Dict[str, Any]:
    """
    辅助函数：将格式化的上下文字符串解析回字典（用于向后兼容）

    注意：这是一个简化的解析器，主要用于测试兼容性
    实际使用中应直接使用 pruner_node 的输出
    """
    if not context_str:
        return {}

    # 简单解析：按 ## 分割，然后解析内容
    result = {}
    current_section = None
    current_content = []

    for line in context_str.split("\n"):
        if line.startswith("## "):
            # 保存上一个 section
            if current_section:
                result[current_section] = _parse_lines_to_dict(current_content)

            # 开始新 section
            current_section = line[3:].strip()
            current_content = []
        elif line.strip():
            current_content.append(line)

    # 保存最后一个 section
    if current_section:
        result[current_section] = _parse_lines_to_dict(current_content)

    return result


def _parse_lines_to_dict(lines: List[str]) -> Any:
    """
    辅助函数：将行列表解析为字典或列表
    """
    if not lines:
        return {}

    result = {}
    for line in lines:
        if ": " in line:
            key, value = line.split(": ", 1)
            # 处理缩进
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                result[key.strip()] = value.strip()
            else:
                # 嵌套结构（简化处理）
                if key not in result:
                    result[key] = []
                result[key].append(value.strip())
        elif line.strip().startswith("- "):
            # 列表项
            if "_list" not in result:
                result["_list"] = []
            result["_list"].append(line.strip()[2:])

    return result
