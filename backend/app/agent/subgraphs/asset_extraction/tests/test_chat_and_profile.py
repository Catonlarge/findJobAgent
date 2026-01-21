"""
Chat & Profile 子图单元测试

测试内容：
1. ProfileLoader 节点：加载用户观察摘要
2. ChatBot 节点：与用户对话
3. Profiler 节点：提取职业信息
4. Chat Router：路由决策
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.subgraphs.asset_extraction.chat_and_profile.nodes import (
    profile_loader_node,
    chat_node,
    profiler_node,
    chat_router,
    _get_username_from_config,
)
from app.agent.subgraphs.asset_extraction.chat_and_profile.state import ChatAndProfileState


class TestGetUsernameFromConfig:
    """测试从 config 获取 username 的辅助函数"""

    def test_get_username_from_valid_config(self, mock_runnable_config):
        """测试从有效的 config 中获取 username"""
        username = _get_username_from_config(mock_runnable_config)
        assert username == "test_user"

    def test_get_username_with_default(self):
        """测试没有 username 时使用默认值"""
        config = {"configurable": {}}
        username = _get_username_from_config(config)
        assert username == "me"

    def test_get_username_with_invalid_type(self):
        """测试 username 类型错误时抛出异常"""
        config = {"configurable": {"username": 123}}
        with pytest.raises(ValueError, match="username must be a string"):
            _get_username_from_config(config)


class TestProfileLoaderNode:
    """测试 ProfileLoader 节点"""

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_or_create_user")
    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_existing_observations_summary")
    def test_profile_loader_new_user(
        self,
        mock_get_summary,
        mock_get_user,
        mock_runnable_config,
        mock_chat_state
    ):
        """测试新用户的观察摘要加载"""
        # 设置 Mock
        mock_user = Mock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        mock_get_summary.return_value = ("", False)

        # 执行
        result = profile_loader_node(mock_chat_state, mock_runnable_config)

        # 验证
        assert "l1_observations_summary" in result
        assert "当前用户画像为空" in result["l1_observations_summary"]
        mock_get_user.assert_called_once_with("test_user")

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_or_create_user")
    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_existing_observations_summary")
    def test_profile_loader_existing_user(
        self,
        mock_get_summary,
        mock_get_user,
        mock_runnable_config,
        mock_chat_state
    ):
        """测试已有用户的观察摘要加载"""
        # 设置 Mock
        mock_user = Mock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user
        existing_summary = "技能: Python\n经验: 3年"
        mock_get_summary.return_value = (existing_summary, True)

        # 执行
        result = profile_loader_node(mock_chat_state, mock_runnable_config)

        # 验证
        assert result["l1_observations_summary"] == existing_summary


class TestChatNode:
    """测试 ChatBot 节点"""

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_llm")
    def test_chat_node_empty_messages(self, mock_get_llm, mock_chat_state, mock_runnable_config):
        """测试空消息时发送欢迎语"""
        mock_chat_state["messages"] = []

        # 执行
        result = chat_node(mock_chat_state, mock_runnable_config)

        # 验证
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        assert "你好" in result["messages"][0].content
        assert result["last_user_message"] is None

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_llm")
    def test_chat_node_with_user_message(
        self,
        mock_get_llm,
        mock_chat_state,
        mock_runnable_config,
        sample_human_message
    ):
        """测试有用户消息时的回应"""
        # 设置 Mock
        mock_llm = Mock()
        mock_llm.invoke.return_value = AIMessage(content="听起来你的技术栈很扎实！")
        mock_get_llm.return_value = mock_llm

        # 设置状态
        mock_chat_state["messages"] = [sample_human_message]
        mock_chat_state["l1_observations_summary"] = "【暂无历史观察记录】"

        # 执行
        result = chat_node(mock_chat_state, mock_runnable_config)

        # 验证
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        assert result["messages"][0].content == "听起来你的技术栈很扎实！"
        assert result["last_user_message"] == sample_human_message

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_llm")
    def test_chat_node_llm_error(self, mock_get_llm, mock_chat_state, mock_runnable_config):
        """测试 LLM 调用失败时的降级处理"""
        # 设置 Mock 抛出异常
        mock_get_llm.side_effect = Exception("LLM service unavailable")

        # 设置状态
        mock_chat_state["messages"] = [HumanMessage(content="你好")]

        # 执行
        result = chat_node(mock_chat_state, mock_runnable_config)

        # 验证：应该返回降级消息
        assert "messages" in result
        assert isinstance(result["messages"][0], AIMessage)
        assert "抱歉" in result["messages"][0].content or "稍后" in result["messages"][0].content


class TestProfilerNode:
    """测试 Profiler 节点"""

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.save_observation_to_l1")
    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_or_create_user")
    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_llm")
    def test_profiler_node_extracts_observations(
        self,
        mock_get_llm,
        mock_get_user,
        mock_save_obs,
        mock_runnable_config,
        sample_human_message,
        mock_profiler_output
    ):
        """测试 Profiler 提取观察"""
        # 设置 Mock
        mock_user = Mock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user

        mock_llm = Mock()
        mock_structured = Mock()
        mock_structured.invoke.return_value = mock_profiler_output
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        mock_save_obs.return_value = True

        # 设置状态
        state = {
            "messages": [sample_human_message],
            "l1_observations_summary": "【暂无历史观察记录】",
            "last_user_message": sample_human_message,
            "session_new_observation_count": 0
        }

        # 执行
        result = profiler_node(state, mock_runnable_config)

        # 验证
        assert "last_turn_analysis" in result
        assert result["last_turn_analysis"]["has_new_info"] is True
        assert result["last_turn_analysis"]["new_observation_count"] == 2
        assert result["session_new_observation_count"] == 2
        # 未达到阈值 10
        assert result["last_turn_analysis"]["is_ready_to_refine"] is False

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_or_create_user")
    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_llm")
    def test_profiler_node_no_user_message(
        self,
        mock_get_llm,
        mock_get_user,
        mock_runnable_config
    ):
        """测试没有用户消息时跳过分析"""
        # 设置状态
        state = {
            "messages": [],
            "l1_observations_summary": "【暂无历史观察记录】",
            "last_user_message": None
        }

        # 执行
        result = profiler_node(state, mock_runnable_config)

        # 验证
        assert result["last_turn_analysis"] is None

    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_or_create_user")
    @patch("app.agent.subgraphs.asset_extraction.chat_and_profile.nodes.get_llm")
    def test_profiler_node_ready_to_refine(
        self,
        mock_get_llm,
        mock_get_user,
        mock_runnable_config,
        sample_human_message,
        mock_profiler_output
    ):
        """测试达到阈值时触发整理阶段"""
        # 设置 Mock
        mock_user = Mock()
        mock_user.id = 1
        mock_get_user.return_value = mock_user

        mock_llm = Mock()
        mock_structured = Mock()
        mock_structured.invoke.return_value = mock_profiler_output
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        # 设置状态：已有 9 条观察，再加 2 条达到 11 条
        state = {
            "messages": [sample_human_message],
            "l1_observations_summary": "【暂无历史观察记录】",
            "last_user_message": sample_human_message,
            "session_new_observation_count": 9
        }

        # 执行
        result = profiler_node(state, mock_runnable_config)

        # 验证
        assert result["last_turn_analysis"]["is_ready_to_refine"] is True
        assert result["session_new_observation_count"] == 11


class TestChatRouter:
    """测试聊天路由"""

    def test_router_continue_chat_no_analysis(self):
        """测试没有分析结果时继续聊天"""
        state: ChatAndProfileState = {"last_turn_analysis": None}
        result = chat_router(state)
        assert result == "continue_chat"

    def test_router_continue_chat_below_threshold(self):
        """测试未达到阈值时继续聊天"""
        state: ChatAndProfileState = {
            "last_turn_analysis": {
                "has_new_info": True,
                "new_observation_count": 2,
                "is_ready_to_refine": False
            }
        }
        result = chat_router(state)
        assert result == "continue_chat"

    def test_router_enter_refinement_above_threshold(self):
        """测试达到阈值时进入整理阶段"""
        state: ChatAndProfileState = {
            "last_turn_analysis": {
                "has_new_info": True,
                "new_observation_count": 2,
                "is_ready_to_refine": True
            }
        }
        result = chat_router(state)
        assert result == "enter_refinement"
