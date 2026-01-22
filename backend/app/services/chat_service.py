"""
聊天服务层

封装聊天业务逻辑，包括：
1. 身份锚定 (Identity Anchoring)：username -> user_db_id
2. 会话容器保证 (Session Container Guarantee)
3. 消息存储与 LangGraph 调用
4. Interrupt 恢复机制：使用 Command(resume=...) 从中断点恢复执行
"""

import uuid
from typing import Optional, Generator, Any
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

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
        4. 检查是否有未完成的 LangGraph interrupt
        5. 如果有 interrupt，使用 Command(resume=...) 恢复执行
        6. 如果没有 interrupt，正常调用图
        7. 流式输出 AI 回复（带消息 ID 去重，防止重复 yield）
        8. 写入数据库（AI 消息）
        9. 更新会话 updated_at

        Interrupt 恢复机制：
        - 使用 graph.get_state(config) 检查是否有未完成的 interrupt
        - 如果 state.next 不为空，说明有 interrupt，使用 Command(resume=...) 恢复
        - 这样可以避免重新执行整个图，直接从中断点继续

        消息去重机制（修复流式重复问题）：
        - 使用 processed_message_ids 记录已处理过的消息 ID
        - 防止后续子图节点（如 Proposer）触发事件时重复 yield 同一条 AI 消息
        - 解决 LangGraph stream_mode="values" 导致的重复输出问题

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
        # 注意：config 中必须传 username，节点内部通过 _get_username_from_config 读取
        config = {
            "configurable": {
                "username": self.username,
                "thread_id": self.thread_id
            }
        }

        # 5. 检查是否有未完成的 interrupt
        state = graph.get_state(config)
        # 注意：state.next 是一个元组，空元组 () 表示没有 interrupt
        # 使用 bool(state.next) 来检查（空元组的布尔值是 False）
        has_interrupt = bool(state.next)

        ai_message_obj: Optional[AIMessage] = None
        full_response = ""

        # 【关键修改】预加载历史消息 UUIDs，赋予去重逻辑"历史记忆"
        # 治本方案：解决 LangGraph stream_mode="values" 输出全量状态导致的历史消息重复处理问题
        # LangGraph 在 resume 时会重新输出完整 State（包含历史消息），如果不预加载历史 UUIDs，
        # 瞬态的 processed_message_ids set() 无法识别已存在的历史消息，导致重复 yield 和重复存库
        from sqlmodel import select
        from app.models.message import ChatMessage

        with Session(get_engine()) as session:
            existing_uuids_result = session.exec(
                select(ChatMessage.msg_uuid)
                .where(ChatMessage.session_id == self.session_db_id)
                .where(ChatMessage.msg_uuid.isnot(None))  # 排除空 UUID
            ).all()
            # all() 返回的是 Row 对象元组，需要提取第一列
            processed_message_ids = {row[0] for row in existing_uuids_result}

        print(f"[ChatService] 预加载历史消息 UUIDs: 共 {len(processed_message_ids)} 条")

        # 【重要】将本次用户消息的 UUID 也加入已处理集合
        # 因为我们在第 2 步就已经存库了，防止流中回显时重复处理
        processed_message_ids.add(user_msg_uuid)

        def process_event(event_data: dict) -> Optional[str]:
            """
            处理 LangGraph stream 事件，提取 AI 消息内容

            Args:
                event_data: LangGraph stream 事件数据

            Returns:
                Optional[str]: 如果有新的 AI 消息，返回内容；否则返回 None
            """
            nonlocal ai_message_obj, full_response

            if "messages" not in event_data:
                return None

            messages = event_data["messages"]
            if not messages:
                return None

            latest_msg = messages[-1]

            # 仅处理 AI 消息，且必须是未处理过的 ID
            if isinstance(latest_msg, AIMessage):
                msg_id = latest_msg.id

                # 检查是否已处理过这条消息
                if msg_id in processed_message_ids:
                    print(f"[ChatService] DEBUG: 跳过重复消息 ID={msg_id}")
                    return None

                # 标记为已处理
                processed_message_ids.add(msg_id)
                print(f"[ChatService] DEBUG: 处理新 AI 消息 ID={msg_id}")

                ai_message_obj = latest_msg
                content = latest_msg.content
                if isinstance(content, str):
                    return content

            return None

        if has_interrupt:
            # 6a. 有 interrupt，使用 Command(resume=...) 恢复执行
            print(f"[ChatService] 检测到未完成的 interrupt，使用 Command(resume=...) 恢复执行")
            print(f"[ChatService] 下一步节点: {state.next}")

            # 构造透传数据包：这个字典会被 human_node 里的 interrupt() 接收
            # 并作为 human_node 的返回值，最终更新到 State["messages"]
            resume_payload = {
                "messages": [
                    HumanMessage(content=user_text, id=user_msg_uuid)
                ]
            }

            # 使用 Command(resume=...) 恢复执行
            # 注意：这里不需要 update= 参数，因为 human_node 会负责 return payload
            # LangGraph 会自动将 human_node 的返回值合并到 EditorState 中
            for event in graph.stream(
                Command(resume=resume_payload),
                config=config,
                stream_mode="values"
            ):
                # 【修改】使用去重逻辑处理事件
                content = process_event(event)
                if content:
                    yield content
                    full_response = content
        else:
            # 6b. 没有 interrupt，正常调用图
            print(f"[ChatService] 正常执行流程")
            inputs = {"messages": [user_message]}

            for event in graph.stream(inputs, config=config, stream_mode="values"):
                # 【修改】使用去重逻辑处理事件
                content = process_event(event)
                if content:
                    yield content
                    full_response = content

        # 7. 写入数据库（AI 消息）
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

            # 8. 更新会话时间戳
            self._touch_session()
            print(f"[ChatService] AI 消息已存库: UUID={ai_msg_uuid}")

    def get_session_id(self) -> int:
        """获取数据库会话 ID"""
        return self.session_db_id

    def get_user_db_id(self) -> int:
        """获取数据库用户 ID"""
        return self.user_db_id
