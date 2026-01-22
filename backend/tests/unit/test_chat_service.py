"""
ChatService 单元测试

测试 ChatService 的核心功能：
1. 身份锚定 (Identity Anchoring)
2. 会话容器保证 (Session Container Guarantee)
3. 消息存储与 LangGraph 调用
4. Interrupt 恢复机制：使用 Command(resume=...) 从中断点恢复执行
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

from app.services.chat_service import ChatService
from app.models.message import MessageRole


class TestChatServiceInit:
    """测试 ChatService 初始化"""

    def test_init_creates_or_gets_user(self, test_db_session, test_user, test_db_engine):
        """测试初始化时创建或获取用户"""
        session_uuid = "test-session-123"

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(username="testuser", session_uuid=session_uuid)

            assert service.username == "testuser"
            assert service.session_uuid == session_uuid
            assert service.user_db_id == test_user.id
            assert service.thread_id == session_uuid

    def test_init_ensures_session_exists(self, test_db_session, test_user, test_db_engine):
        """测试初始化时确保会话容器存在"""
        session_uuid = "new-session-456"

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(username="testuser", session_uuid=session_uuid)

            assert service.session_db_id is not None
            assert service.chat_session.user_id == test_user.id
            assert service.chat_session.session_uuid == session_uuid


class TestChatServiceSendMessageNormalFlow:
    """测试 ChatService 正常流程（无 interrupt）"""

    def test_send_message_without_interrupt(
        self, test_db_session, test_user, test_chat_session, test_db_engine
    ):
        """测试没有 interrupt 时的正常消息发送"""
        # 创建 mock graph
        mock_graph = Mock()
        mock_state = Mock()
        mock_state.next = None  # 没有 interrupt
        mock_graph.get_state.return_value = mock_state

        # 模拟图执行流式输出
        mock_ai_message = AIMessage(
            id="ai-msg-123",
            content="你好！我是AI助手。"
        )
        mock_graph.stream.return_value = [
            {"messages": [mock_ai_message]}
        ]

        # 创建 ChatService
        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(
                username="testuser",
                session_uuid=test_chat_session.session_uuid
            )

            # 发送消息
            responses = list(service.send_message_stream(
                user_text="你好",
                graph=mock_graph
            ))

            # 验证响应
            assert len(responses) == 1
            assert responses[0] == "你好！我是AI助手。"

            # 验证图被正确调用
            mock_graph.get_state.assert_called_once()
            mock_graph.stream.assert_called_once()

            # 验证 stream 的参数
            call_args = mock_graph.stream.call_args
            inputs = call_args[0][0]
            config = call_args[1]["config"]

            # 应该传入 messages
            assert "messages" in inputs
            assert len(inputs["messages"]) == 1
            assert isinstance(inputs["messages"][0], HumanMessage)
            assert inputs["messages"][0].content == "你好"

            # config 应该包含 username 和 thread_id
            assert config["configurable"]["username"] == "testuser"
            assert config["configurable"]["thread_id"] == test_chat_session.session_uuid

    def test_send_message_stores_user_message(
        self, test_db_session, test_user, test_chat_session, test_db_engine
    ):
        """测试用户消息被正确存储"""
        mock_graph = Mock()
        mock_state = Mock()
        mock_state.next = None
        mock_graph.get_state.return_value = mock_state
        mock_graph.stream.return_value = [
            {"messages": [AIMessage(id="ai-1", content="回复")]}
        ]

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(
                username="testuser",
                session_uuid=test_chat_session.session_uuid
            )

            list(service.send_message_stream(
                user_text="测试消息",
                graph=mock_graph
            ))

            # 验证用户消息被存储
            from app.repositories.session_repository import SessionRepository
            from app.db.init_db import get_engine

            session_repo = SessionRepository(test_db_session)
            messages = session_repo.get_messages_by_session_id(service.session_db_id)

            # 应该有两条消息：用户消息 + AI 消息
            assert len(messages) >= 1
            user_messages = [m for m in messages if m.role == MessageRole.USER]
            assert len(user_messages) >= 1
            assert user_messages[-1].content == "测试消息"

    def test_send_message_stores_ai_message(
        self, test_db_session, test_user, test_chat_session, test_db_engine
    ):
        """测试 AI 消息被正确存储"""
        mock_graph = Mock()
        mock_state = Mock()
        mock_state.next = None
        mock_graph.get_state.return_value = mock_state

        ai_response = "这是AI的回复"
        mock_graph.stream.return_value = [
            {"messages": [AIMessage(id="ai-123", content=ai_response)]}
        ]

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(
                username="testuser",
                session_uuid=test_chat_session.session_uuid
            )

            list(service.send_message_stream(
                user_text="用户消息",
                graph=mock_graph
            ))

            # 验证 AI 消息被存储
            from app.repositories.session_repository import SessionRepository

            session_repo = SessionRepository(test_db_session)
            messages = session_repo.get_messages_by_session_id(service.session_db_id)

            ai_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]
            assert len(ai_messages) >= 1
            assert ai_messages[-1].content == ai_response


class TestChatServiceInterruptResume:
    """测试 ChatService Interrupt 恢复机制"""

    def test_send_message_with_interrupt_uses_command_resume(
        self, test_db_session, test_user, test_chat_session, test_db_engine
    ):
        """测试有 interrupt 时使用 Command(resume=...) 恢复执行"""
        mock_graph = Mock()
        mock_state = Mock()
        mock_state.next = ["human_node"]  # 有 interrupt
        mock_graph.get_state.return_value = mock_state

        # 模拟恢复执行后的输出
        mock_graph.stream.return_value = [
            {"messages": [AIMessage(id="ai-456", content="修改完成")]}
        ]

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(
                username="testuser",
                session_uuid=test_chat_session.session_uuid
            )

            # 发送修改意见
            responses = list(service.send_message_stream(
                user_text="把Python改成Java",
                graph=mock_graph
            ))

            # 验证响应
            assert len(responses) >= 1
            assert "修改完成" in responses[-1]

            # 验证使用了 Command(resume=...)
            call_args = mock_graph.stream.call_args
            first_arg = call_args[0][0]

            # 应该是 Command(resume=...) 而不是 inputs
            assert isinstance(first_arg, Command)
            # Command 的 resume 参数应该是一个包含 messages 的字典
            assert isinstance(first_arg.resume, dict)
            assert "messages" in first_arg.resume
            assert len(first_arg.resume["messages"]) == 1
            assert isinstance(first_arg.resume["messages"][0], HumanMessage)
            assert first_arg.resume["messages"][0].content == "把Python改成Java"

            # config 应该正确
            config = call_args[1]["config"]
            assert config["configurable"]["username"] == "testuser"
            assert config["configurable"]["thread_id"] == test_chat_session.session_uuid

    def test_send_message_without_interrupt_uses_normal_inputs(
        self, test_db_session, test_user, test_chat_session, test_db_engine
    ):
        """测试没有 interrupt 时使用正常的 inputs"""
        mock_graph = Mock()
        mock_state = Mock()
        mock_state.next = None  # 没有 interrupt
        mock_graph.get_state.return_value = mock_state

        user_text = "你好"
        mock_graph.stream.return_value = [
            {"messages": [AIMessage(id="ai-789", content="你好！")]}
        ]

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(
                username="testuser",
                session_uuid=test_chat_session.session_uuid
            )

            list(service.send_message_stream(
                user_text=user_text,
                graph=mock_graph
            ))

            # 验证使用了正常的 inputs（不是 Command）
            call_args = mock_graph.stream.call_args
            first_arg = call_args[0][0]

            # 应该是 dict 类型的 inputs
            assert isinstance(first_arg, dict)
            assert "messages" in first_arg
            assert isinstance(first_arg["messages"], list)
            assert first_arg["messages"][0].content == user_text

    def test_interrupt_flow_preserves_session_context(
        self, test_db_session, test_user, test_chat_session, test_db_engine
    ):
        """测试 interrupt 流程保持会话上下文"""
        mock_graph = Mock()

        # 第一次调用：没有 interrupt
        mock_state_no_interrupt = Mock()
        mock_state_no_interrupt.next = None

        # 第二次调用：有 interrupt
        mock_state_with_interrupt = Mock()
        mock_state_with_interrupt.next = ["human_node"]

        mock_graph.get_state.side_effect = [
            mock_state_no_interrupt,
            mock_state_with_interrupt
        ]

        mock_graph.stream.return_value = [
            {"messages": [AIMessage(id="ai-1", content="回复")]}
        ]

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(
                username="testuser",
                session_uuid=test_chat_session.session_uuid
            )

            # 第一次正常调用
            list(service.send_message_stream("第一次消息", graph=mock_graph))

            # 第二次调用（有 interrupt）
            list(service.send_message_stream("修改意见", graph=mock_graph))

            # 验证两次调用都使用了相同的 config
            assert mock_graph.stream.call_count == 2

            first_call_config = mock_graph.stream.call_args_list[0][1]["config"]
            second_call_config = mock_graph.stream.call_args_list[1][1]["config"]

            assert first_call_config == second_call_config
            assert first_call_config["configurable"]["username"] == "testuser"
            assert first_call_config["configurable"]["thread_id"] == test_chat_session.session_uuid


class TestChatServiceConfigMapping:
    """测试 ChatService 配置映射"""

    def test_config_uses_username_not_user_id(
        self, test_db_session, test_user, test_chat_session, test_db_engine
    ):
        """测试 config 使用 username 而不是 user_id"""
        mock_graph = Mock()
        mock_state = Mock()
        mock_state.next = None
        mock_graph.get_state.return_value = mock_state
        mock_graph.stream.return_value = []

        with patch("app.services.chat_service.get_engine", return_value=test_db_engine):
            service = ChatService(
                username="testuser",
                session_uuid=test_chat_session.session_uuid
            )

            list(service.send_message_stream("测试", graph=mock_graph))

            # 验证 config 使用 username
            call_args = mock_graph.stream.call_args
            config = call_args[1]["config"]

            # 应该有 username
            assert "username" in config["configurable"]
            assert config["configurable"]["username"] == "testuser"

            # 不应该有 user_id（这是旧的 bug）
            # 注意：如果同时存在 user_id 和 username，节点会优先读取 username
            # 但为了清晰，应该只传 username
