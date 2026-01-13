"""
上下文剪枝器单元测试

测试剪枝器根据意图从用户画像中提取相关字段的功能。
符合 T2-02 设计规范：配置驱动模式
"""

import sys
import os
import pytest

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.models.chat import ChatIntent
from app.agent.nodes.pruner import (
    pruner_node,
    extract_resume_fields,
    extract_interview_fields,
    extract_onboarding_fields,
    extract_general_fields,
    extract_sections_by_key,
    filter_empty_values,
    format_context,
    SECTION_TITLES,
    INTENT_MAPPING
)


class TestPrunerNode:
    """测试剪枝器主节点 - T2-02 配置驱动模式"""

    @pytest.fixture
    def sample_user_profile(self):
        """创建示例用户画像数据"""
        return {
            "basic_info": {
                "姓名": "张三",
                "邮箱": "zhangsan@email.com",
                "电话": "13800138000",
                "城市": "北京",
                "学校": "清华大学",
                "专业": "计算机科学与技术",
                "毕业年份": "2020"
            },
            "profile_sections": [
                {
                    "section_key": "work_experience",
                    "content": {
                        "公司": "阿里巴巴",
                        "职位": "高级软件工程师",
                        "时间": "2020-至今",
                        "主要职责": "负责前端架构设计和开发，带领团队完成多个重要项目"
                    }
                },
                {
                    "section_key": "skills",
                    "content": {
                        "前端技术": "React, Vue, TypeScript",
                        "后端技术": "Node.js, Python, Go",
                        "熟练度": "高级"
                    }
                },
                {
                    "section_key": "education",
                    "content": {
                        "学校": "清华大学",
                        "专业": "计算机科学与技术",
                        "学位": "学士",
                        "成绩": "GPA: 3.8/4.0"
                    }
                }
            ]
        }

    def test_pruner_node_resume_refine(self, sample_user_profile):
        """测试简历优化意图下的剪枝结果"""
        state = {
            "user_profile": sample_user_profile,
            "current_intent": ChatIntent.RESUME_REFINE
        }

        result = pruner_node(state)

        assert "pruned_context_str" in result
        assert isinstance(result["pruned_context_str"], str)

        # T2-02: 使用 SECTION_TITLES 中定义的标题
        expected_title = SECTION_TITLES["basic_info"]
        assert f"## {expected_title}" in result["pruned_context_str"]
        assert "姓名: 张三" in result["pruned_context_str"]

        # T2-02: resume_refine 加载 education, work_experience, skills
        assert f"## {SECTION_TITLES['education']}" in result["pruned_context_str"]
        assert "清华大学" in result["pruned_context_str"]
        assert f"## {SECTION_TITLES['work_experience']}" in result["pruned_context_str"]
        assert "阿里巴巴" in result["pruned_context_str"]
        assert f"## {SECTION_TITLES['skills']}" in result["pruned_context_str"]
        assert "React" in result["pruned_context_str"]

    def test_pruner_node_interview_prep(self, sample_user_profile):
        """测试面试准备意图下的剪枝结果"""
        state = {
            "user_profile": sample_user_profile,
            "current_intent": ChatIntent.INTERVIEW_PREP
        }

        result = pruner_node(state)

        assert "pruned_context_str" in result
        assert isinstance(result["pruned_context_str"], str)

        # T2-02: interview_prep 加载 basic_info, project_details, behavioral_traits, skills
        assert f"## {SECTION_TITLES['basic_info']}" in result["pruned_context_str"]
        assert "张三" in result["pruned_context_str"]
        assert f"## {SECTION_TITLES['skills']}" in result["pruned_context_str"]

        # T2-02: 面试场景不加载 education（从 INTENT_MAPPING['interview_prep'] 中排除）
        assert SECTION_TITLES['education'] not in result["pruned_context_str"]

    def test_pruner_node_general_chat(self, sample_user_profile):
        """测试通用聊天意图下的剪枝结果"""
        state = {
            "user_profile": sample_user_profile,
            "current_intent": ChatIntent.GENERAL_CHAT
        }

        result = pruner_node(state)

        assert "pruned_context_str" in result
        assert isinstance(result["pruned_context_str"], str)

        # T2-02: default 只加载 basic_info, summary
        assert f"## {SECTION_TITLES['basic_info']}" in result["pruned_context_str"]
        assert "张三" in result["pruned_context_str"]

    def test_pruner_node_default_intent(self):
        """测试默认意图（当未提供意图时的回退）"""
        state = {
            "user_profile": {
                "basic_info": {"姓名": "李四"}
            }
            # 未提供 current_intent，应使用默认值 GENERAL_CHAT
        }

        result = pruner_node(state)

        assert "pruned_context_str" in result
        assert "张三" not in result["pruned_context_str"]
        assert "李四" in result["pruned_context_str"]

    def test_pruner_node_onboarding(self):
        """测试引导注册场景的剪枝结果"""
        state = {
            "user_profile": {
                "basic_info": {
                    "姓名": "王五",
                    "邮箱": "wangwu@email.com"
                },
                "profile_sections": []
            },
            "current_intent": ChatIntent.ONBOARDING
        }

        result = pruner_node(state)

        assert "pruned_context_str" in result
        assert f"## {SECTION_TITLES['basic_info']}" in result["pruned_context_str"]
        assert "王五" in result["pruned_context_str"]


class TestConfigurationDriven:
    """测试 T2-02 配置驱动模式的核心特性"""

    def test_section_titles_has_all_keys(self):
        """验证 SECTION_TITLES 包含所有必需的键"""
        required_keys = [
            "basic_info", "education", "work_experience",
            "projects_summary", "project_details", "skills",
            "behavioral_traits", "summary"
        ]
        for key in required_keys:
            assert key in SECTION_TITLES, f"SECTION_TITLES 缺少键: {key}"
            assert isinstance(SECTION_TITLES[key], str), f"SECTION_TITLES[{key}] 应该是字符串"

    def test_intent_mapping_has_all_intents(self):
        """验证 INTENT_MAPPING 包含所有意图"""
        required_intents = ["resume_refine", "interview_prep", "onboarding", "default"]
        for intent in required_intents:
            assert intent in INTENT_MAPPING, f"INTENT_MAPPING 缺少意图: {intent}"
            assert isinstance(INTENT_MAPPING[intent], list), f"INTENT_MAPPING[{intent}] 应该是列表"

    def test_resume_refine_intent_config(self):
        """验证 resume_refine 意图的配置符合 T2-02 规范"""
        config = INTENT_MAPPING["resume_refine"]

        # T2-02: 简历场景加载 basic_info, education, work_experience, projects_summary, skills
        assert "basic_info" in config
        assert "education" in config
        assert "work_experience" in config
        assert "projects_summary" in config
        assert "skills" in config

        # T2-02: 简历场景不加载 project_details（太长）和 behavioral_traits（不写性格）
        assert "project_details" not in config
        assert "behavioral_traits" not in config

    def test_interview_prep_intent_config(self):
        """验证 interview_prep 意图的配置符合 T2-02 规范"""
        config = INTENT_MAPPING["interview_prep"]

        # T2-02: 面试场景加载 basic_info, project_details, behavioral_traits, skills
        assert "basic_info" in config
        assert "project_details" in config
        assert "behavioral_traits" in config
        assert "skills" in config

        # T2-02: 面试场景不加载 projects_summary（信息量不足）和 education（通常不问细节）
        assert "projects_summary" not in config
        assert "education" not in config

    def test_default_intent_config(self):
        """验证 default 意图的配置符合 T2-02 规范"""
        config = INTENT_MAPPING["default"]

        # T2-02: 闲聊场景极简，只加载 basic_info, summary
        assert "basic_info" in config
        assert "summary" in config
        assert len(config) == 2

    def test_soft_degradation_when_data_missing(self):
        """测试软降级：数据缺失时不报错，自动跳过"""
        state = {
            "user_profile": {
                "basic_info": {"姓名": "测试用户"},
                "profile_sections": []  # 没有其他数据
            },
            "current_intent": ChatIntent.RESUME_REFINE
        }

        # 应该正常返回，不抛出异常
        result = pruner_node(state)
        assert "pruned_context_str" in result

        # 只应该包含 basic_info
        assert SECTION_TITLES["basic_info"] in result["pruned_context_str"]
        # 不应该包含缺失的字段
        assert SECTION_TITLES["education"] not in result["pruned_context_str"]


class TestExtractFields:
    """测试向后兼容的字段提取函数"""

    @pytest.fixture
    def complex_user_profile(self):
        """创建更复杂的用户画像数据"""
        return {
            "basic_info": {
                "姓名": "赵六",
                "邮箱": "zhaoliu@email.com",
                "电话": "13800138001",
                "城市": "上海",
                "expected_position": "产品经理",
                "期望行业": "互联网",
                "期望公司": "字节跳动"
            },
            "profile_sections": [
                {
                    "section_key": "work_experience",
                    "content": {
                        "公司": "腾讯",
                        "职位": "产品主管",
                        "时间": "2019-2023",
                        "主要职责": "负责QQ音乐产品线的规划和执行"
                    }
                },
                {
                    "section_key": "skills",
                    "content": {
                        "产品能力": "需求分析、用户研究、数据分析",
                        "工具": "Figma、Axure、SQL"
                    }
                },
                {
                    "section_key": "behavioral_traits",
                    "content": {
                        "性格": "外向、善于沟通",
                        "价值观": "用户第一、数据驱动"
                    }
                }
            ]
        }

    def test_extract_resume_fields(self, complex_user_profile):
        """测试简历字段提取 - 向后兼容"""
        result = extract_resume_fields(complex_user_profile)

        # 向后兼容：应该返回字典格式的结果
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_extract_interview_fields(self, complex_user_profile):
        """测试面试字段提取 - 向后兼容"""
        result = extract_interview_fields(complex_user_profile)

        # 向后兼容：应该返回字典格式的结果
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_extract_onboarding_fields(self):
        """测试引导注册字段提取"""
        user_profile = {
            "basic_info": {
                "姓名": "陈七",
                "邮箱": "chenqi@email.com"
            },
            "profile_sections": [
                {"section_key": "skills", "content": {"技术": "Python"}}
            ]
        }

        result = extract_onboarding_fields(user_profile)

        assert "基本信息" in result
        assert "陈七" in result["基本信息"]["姓名"]
        assert "现有画像切片" in result
        assert "skills" in result["现有画像切片"]

    def test_extract_general_fields(self):
        """测试通用字段提取 - 向后兼容"""
        user_profile = {
            "basic_info": {
                "姓名": "周八",
                "职业": "设计师",
                "城市": "深圳"
            },
            "profile_sections": [
                {
                    "section_key": "skills",
                    "content": {"设计工具": "Photoshop, Sketch"}
                }
            ]
        }

        result = extract_general_fields(user_profile)

        # 向后兼容：应该返回字典格式的结果
        assert isinstance(result, dict)


class TestUtilityFunctions:
    """测试工具函数"""

    def test_filter_empty_values(self):
        """测试空值过滤功能"""
        test_data = {
            "姓名": "张三",
            "年龄": 25,
            "邮箱": "",
            "电话": None,
            "地址": {},
            "经验": [],
            "教育": {
                "学校": "清华",
                "专业": None,
                "成绩": []
            }
        }

        result = filter_empty_values(test_data)

        assert "姓名" in result
        assert "年龄" in result
        assert "邮箱" not in result
        assert "电话" not in result
        assert "地址" not in result
        assert "经验" not in result
        # 嵌套字典也处理了
        assert "教育" in result
        assert "专业" not in result["教育"]
        assert "成绩" not in result["教育"]

    def test_format_context_simple(self):
        """测试简单数据格式化"""
        test_data = {
            "个人信息": {
                "姓名": "张三",
                "年龄": 28
            },
            "技能": ["Python", "React", "Go"]
        }

        result = format_context(test_data)

        assert isinstance(result, str)
        assert "## 个人信息" in result
        assert "姓名: 张三" in result
        assert "年龄: 28" in result
        assert "- Python" in result
        assert "- React" in result

    def test_format_context_nested_dict(self):
        """测试嵌套字典格式化"""
        test_data = {
            "项目经验": [
                {
                    "项目名称": "电商平台",
                    "角色": "全栈工程师",
                    "技术栈": ["React", "Node.js", "MongoDB"]
                }
            ]
        }

        result = format_context(test_data)

        assert "## 项目经验" in result
        assert "1." in result
        assert "项目名称: 电商平台" in result
        assert "- React" in result

    def test_format_context_empty(self):
        """测试空数据格式化"""
        result = format_context({})

        assert result == ""


class TestExtractSectionsByKey:
    """测试从画像切片中提取内容的功能"""

    def test_extract_single_section(self):
        """测试提取单个切片"""
        profile_sections = [
            {
                "section_key": "skills",
                "content": {"技术": "Python, JavaScript"}
            }
        ]

        result = extract_sections_by_key(profile_sections, "skills")

        assert "技术" in result
        assert "Python" in result["技术"]

    def test_extract_multiple_sections(self):
        """测试提取多个同类型切片"""
        profile_sections = [
            {
                "section_key": "work_experience",
                "content": {"公司": "阿里", "职位": "工程师"}
            },
            {
                "section_key": "work_experience",
                "content": {"公司": "腾讯", "职位": "高级工程师"}
            }
        ]

        result = extract_sections_by_key(profile_sections, "work_experience")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["公司"] == "阿里"
        assert result[1]["公司"] == "腾讯"

    def test_extract_nonexistent_section(self):
        """测试提取不存在的切片"""
        profile_sections = [
            {
                "section_key": "skills",
                "content": {"技术": "Python"}
            }
        ]

        result = extract_sections_by_key(profile_sections, "education")

        assert result == []

    def test_extract_empty_sections(self):
        """测试空切片列表"""
        result = extract_sections_by_key([], "skills")

        assert result == []
