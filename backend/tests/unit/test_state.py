"""
AgentState 和 ScoredEvaluation 的单元测试
测试 LangGraph 状态结构和 LLM 结构化输出模式
"""

import sys
import os
import pytest
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# 导入待测试的模块
from app.agent.state import AgentState, ScoredEvaluation
from app.models import ChatIntent


class TestScoredEvaluation:
    """测试 ScoredEvaluation 结构化输出模式"""

    def test_scored_evaluation_creation(self):
        """测试创建有效的 ScoredEvaluation 对象"""
        evaluation = ScoredEvaluation(
            analysis_thought="这是一个详细的思考过程：1. 分析用户需求 2. 评估匹配度 3. 给出建议",
            score=8.5,
            evaluation_criteria=["技能匹配度", "经验相关性", "教育背景"],
            suggestions=["可以增加项目经验描述", "优化技能关键词"],
            matches_requirements=True
        )

        assert evaluation.analysis_thought is not None
        assert evaluation.score == 8.5
        assert len(evaluation.evaluation_criteria) == 3
        assert len(evaluation.suggestions) == 2
        assert evaluation.matches_requirements is True

    def test_scored_evaluation_from_dict(self):
        """测试从字典创建 ScoredEvaluation"""
        data = {
            "analysis_thought": "这是完整的分析结果和评估过程的详细说明",
            "score": 7.0,
            "evaluation_criteria": ["测试标准1", "测试标准2"],
            "suggestions": ["建议1", "建议2"],
            "matches_requirements": False
        }

        evaluation = ScoredEvaluation(**data)
        assert evaluation.score == 7.0
        assert evaluation.matches_requirements is False

    def test_scored_evaluation_minimal_data(self):
        """测试使用最少必需字段创建"""
        evaluation = ScoredEvaluation(
            analysis_thought="这是简化的分析思考过程",
            score=5.0
        )

        assert evaluation.analysis_thought == "这是简化的分析思考过程"
        assert evaluation.score == 5.0
        assert evaluation.evaluation_criteria == []
        assert evaluation.suggestions == []
        assert evaluation.matches_requirements is False


class TestAgentState:
    """测试 AgentState 状态结构"""

    def test_agent_state_creation(self):
        """测试创建完整的 AgentState"""

        # 创建测试消息
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": "帮我优化简历"},
            {"role": "assistant", "content": "好的，请提供你的求职意向"}
        ]

        # 创建评估结果
        evaluation = ScoredEvaluation(
            analysis_thought="用户需要简历优化服务",
            score=9.0
        )

        # 创建状态
        state = AgentState(
            messages=messages,
            pruned_context_str="求职意向: 前端工程师\n工作经验: 3年\n技能: React, Vue",
            user_profile={"name": "测试用户", "experience": "3年"},
            current_intent=ChatIntent.RESUME_REFINE,
            evaluation_result=evaluation,
            generated_artifact="优化后的简历内容...",
            iteration_count=1,
            quality_check_passed=True
        )

        assert len(state["messages"]) == 2
        assert "前端工程师" in state["pruned_context_str"]
        assert state["current_intent"] == ChatIntent.RESUME_REFINE
        assert state["evaluation_result"].score == 9.0
        assert state["iteration_count"] == 1
        assert state["quality_check_passed"] is True

    def test_agent_state_required_fields(self):
        """测试创建包含必需字段的 AgentState"""
        state = AgentState(
            messages=[],
            pruned_context_str="",
            user_profile={}
        )

        assert state["messages"] == []
        assert state["pruned_context_str"] == ""
        assert state["user_profile"] == {}

    def test_agent_state_pruned_context_field(self):
        """测试 pruned_context_str 字段的存在和正确使用"""
        context = """
        原始数据:
        - 姓名: 张三
        - 年龄: 28
        - 工作经验: 5年
        - 求职意向: Java工程师
        - 教育背景: 本科

        剪枝后保留:
        - 工作经验: 5年
        - 求职意向: Java工程师
        - 技能: Spring Boot, MySQL
        """

        state = AgentState(
            messages=[],
            pruned_context_str=context,
            user_profile={}
        )

        # 验证 pruned_context_str 字段存在且包含数据
        assert state["pruned_context_str"] == context
        assert "剪枝后保留" in state["pruned_context_str"]
        assert "Java工程师" in state["pruned_context_str"]

    def test_agent_state_optional_fields(self):
        """测试可选字段的正确处理"""
        state = AgentState(
            messages=[{"role": "user", "content": "hi"}],
            pruned_context_str="测试上下文",
            user_profile={"test": "data"},
            current_intent=ChatIntent.GENERAL_CHAT
        )

        # 验证可选字段未设置时为 None 或默认值
        assert state.get("evaluation_result") is None
        assert state.get("generated_artifact") is None
        assert state.get("iteration_count", 0) == 0  # 使用 get 方法提供默认值
        assert state.get("quality_check_passed", False) is False  # 使用 get 方法提供默认值

    def test_chat_intent_integration(self):
        """测试 ChatIntent 枚举的正确集成"""
        # 测试不同的意图
        for intent in ChatIntent:
            state = AgentState(
                messages=[],
                pruned_context_str="",
                user_profile={},
                current_intent=intent
            )
            assert state["current_intent"] == intent

    def test_agent_state_mutability(self):
        """测试 AgentState 的可变性"""
        state = AgentState(
            messages=[{"role": "user", "content": "初始消息"}],
            pruned_context_str="初始上下文",
            user_profile={}
        )

        # 修改消息列表
        state["messages"].append({"role": "assistant", "content": "回复消息"})
        assert len(state["messages"]) == 2

        # 修改上下文字符串
        state["pruned_context_str"] = "更新后的上下文"
        assert state["pruned_context_str"] == "更新后的上下文"

        # 添加新字段
        state["new_field"] = "新值"
        assert state["new_field"] == "新值"


class TestSchemaCompatibility:
    """测试与 LLM 和 LangGraph 的兼容性"""

    def test_scored_evaluation_json_serialization(self):
        """测试 ScoredEvaluation 的 JSON 序列化"""
        import json

        analysis_text = "这是详细的分析思考过程的完整描述"
        evaluation = ScoredEvaluation(
            analysis_thought=analysis_text,
            score=7.5,
            evaluation_criteria=["标准1", "标准2"],
            suggestions=["建议1"],
            matches_requirements=True
        )

        # 转换为字典
        eval_dict = evaluation.model_dump()

        # 验证所有字段都存在
        assert "analysis_thought" in eval_dict
        assert "score" in eval_dict
        assert "evaluation_criteria" in eval_dict
        assert "suggestions" in eval_dict
        assert "matches_requirements" in eval_dict

        # 验证分析文本正确存储
        assert eval_dict["analysis_thought"] == analysis_text

        # 验证可以序列化为 JSON（不检查具体内容，只验证序列化成功）
        json_str = json.dumps(eval_dict, ensure_ascii=False)
        assert len(json_str) > 0  # 确保序列化成功且不为空

    def test_agent_state_dict_behavior(self):
        """测试 AgentState 的字典行为"""
        state = AgentState(
            messages=[],
            pruned_context_str="测试",
            user_profile={}
        )

        # 测试字典方法
        assert "messages" in state
        assert state.get("pruned_context_str") == "测试"
        assert state.get("non_existent", "default") == "default"

        keys = list(state.keys())
        assert "messages" in keys
        assert "pruned_context_str" in keys
        assert "user_profile" in keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
