"""
聊天服务层

封装聊天业务逻辑，包括：
1. 身份锚定 (Identity Anchoring)：username -> user_db_id
2. 会话容器保证 (Session Container Guarantee)
3. 消息存储与 LangGraph 调用
"""

import uuid
from typing import Optional, Generator, Any
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage

from app.db.init_db import get_engine
from app.repositories.user_repository import UserRepository
from app.repositories.session_repository import SessionRepository
from app.models.message import MessageRole


class ChatService:
    """
    聊天服务类

    核心职责：
    1. 初始化时完成身份转换：String -> Integer
    2. 确保会话容器存在（懒加载）
    3. 提供发送消息接口（自动存储 + 调用图 + 更新会话时间）

    使用示例：
        service = ChatService(username="me", thread_id="session_001")
        for chunk in service.send_message_stream("我会 Python"):
            print(chunk, end="", flush=True)
    """

    def __init__(self, username: str, session_uuid: str):
        """
        初始化服务，完成身份锚定和会话容器保证

        Args:
            username: 用户名（字符串）
            session_uuid: 前端会话 UUID（实践中等于 LangGraph thread_id）
        """
        from sqlmodel import Session

        self.username = username
        self.session_uuid = session_uuid
        self.thread_id = session_uuid  # thread_id 等于 session_uuid

        # 1. 身份锚定：username -> user_db_id
        with Session(get_engine()) as session:
            user_repo = UserRepository(session)
            self.user_db_id = user_repo.get_or_create(username).id

        print(f"[ChatService] 初始化: 用户 '{username}' -> 数据库 ID [{self.user_db_id}]")

        # 2. 会话容器保证
        with Session(get_engine()) as session:
            session_repo = SessionRepository(session)
            self.chat_session = session_repo.ensure_session_exists(
                user_id=self.user_db_id,
                session_uuid=session_uuid
            )

        self.session_db_id = self.chat_session.id
        print(f"[ChatService] 会话容器就绪: DB ID [{self.session_db_id}], session_uuid/thread_id [{session_uuid}]")

    def _touch_session(self):
        """
        更新会话的 updated_at 时间戳

        每次有新消息时调用，确保会话列表按最新活动时间排序正确
        """
        from sqlmodel import Session
        from app.models.chat import ChatSession

        with Session(get_engine()) as session:
            chat_session = session.get(ChatSession, self.session_db_id)
            if chat_session:
                chat_session.updated_at = datetime.utcnow()
                session.add(chat_session)
                session.commit()

    def send_message_stream(
        self,
        user_text: str,
        graph: Any
    ) -> Generator[str, None, None]:
        """
        发送消息并流式获取 AI 回复

        流程：
        1. 生成用户消息 UUID
        2. 立即写入数据库（用户消息）
        3. 更新会话 updated_at
        4. 调用 LangGraph 子图
        5. 流式输出 AI 回复
        6. 写入数据库（AI 消息）
        7. 更新会话 updated_at

        Args:
            user_text: 用户输入文本
            graph: 编译后的 LangGraph 实例

        Yields:
            str: AI 回复的文本片段（流式）
        """
        from sqlmodel import Session

        # 1. 准备用户消息（手动生成 UUID）
        user_msg_uuid = str(uuid.uuid4())
        user_message = HumanMessage(content=user_text, id=user_msg_uuid)

        # 2. 立即写入数据库（用户消息）
        with Session(get_engine()) as session:
            session_repo = SessionRepository(session)
            session_repo.create_message(
                session_id=self.session_db_id,
                role=MessageRole.USER,
                content=user_text,
                msg_uuid=user_msg_uuid
            )

        # 3. 更新会话时间戳
        self._touch_session()
        print(f"[ChatService] 用户消息已存库: UUID={user_msg_uuid}")

        # 4. 准备 LangGraph 配置
        # 注意：config 中传 username（字符串），节点内部再根据需要查询整数 ID
        config = {
            "configurable": {
                "user_id": self.username,  # 传字符串 username
                "thread_id": self.thread_id
            }
        }

        # 5. 调用图并流式输出
        inputs = {"messages": [user_message]}
        ai_message_obj: Optional[AIMessage] = None
        full_response = ""

        for event in graph.stream(inputs, config=config, stream_mode="values"):
            # 捕获 AI 生成的消息
            if "messages" in event:
                messages = event["messages"]
                if messages:
                    latest_msg = messages[-1]
                    if isinstance(latest_msg, AIMessage):
                        ai_message_obj = latest_msg
                        content = latest_msg.content
                        if isinstance(content, str):
                            # 流式输出
                            yield content
                            full_response = content

        # 6. 写入数据库（AI 消息）
        if ai_message_obj:
            ai_msg_uuid = ai_message_obj.id
            with Session(get_engine()) as session:
                session_repo = SessionRepository(session)
                session_repo.create_message(
                    session_id=self.session_db_id,
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    msg_uuid=ai_msg_uuid
                )

            # 7. 更新会话时间戳
            self._touch_session()
            print(f"[ChatService] AI 消息已存库: UUID={ai_msg_uuid}")

    def get_session_id(self) -> int:
        """获取数据库会话 ID"""
        return self.session_db_id

    def get_user_db_id(self) -> int:
        """获取数据库用户 ID"""
        return self.user_db_id
