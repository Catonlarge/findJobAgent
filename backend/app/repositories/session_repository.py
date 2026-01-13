"""
会话管理 Repository
提供 chat_sessions 和 chat_messages 的增删改查操作
"""

from typing import List, Optional, Dict, Any

from sqlmodel import Session, select, col

from app.models.chat import ChatSession, ChatIntent
from app.models.message import ChatMessage, MessageRole, UserFeedback


class SessionRepository:
    """
    会话管理数据访问对象
    封装所有与 chat_sessions 和 chat_messages 表相关的数据库操作
    """

    def __init__(self, session: Session):
        """
        初始化 Repository

        Args:
            session: SQLModel 数据库会话
        """
        self.session = session

    # ==================== ChatSession 操作 ====================

    def create_session(
        self,
        user_id: int,
        thread_id: str,
        intent: ChatIntent,
        title: str,
        context_data: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """
        创建新会话

        Args:
            user_id: 用户 ID
            thread_id: LangGraph Checkpoint ID
            intent: 会话意图枚举
            title: 会话标题
            context_data: 环境配置（可选）

        Returns:
            创建的 ChatSession 对象
        """
        session = ChatSession(
            user_id=user_id,
            thread_id=thread_id,
            intent=intent,
            title=title,
            context_data=context_data or {}
        )
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session

    def get_session_by_id(self, session_id: int) -> Optional[ChatSession]:
        """
        根据 ID 获取会话

        Args:
            session_id: 会话 ID

        Returns:
            ChatSession 对象，不存在则返回 None
        """
        return self.session.get(ChatSession, session_id)

    def get_session_by_thread_id(self, thread_id: str) -> Optional[ChatSession]:
        """
        根据 thread_id 获取会话（用于 LangGraph Checkpoint 恢复）

        Args:
            thread_id: LangGraph Checkpoint ID

        Returns:
            ChatSession 对象，不存在则返回 None
        """
        statement = select(ChatSession).where(ChatSession.thread_id == thread_id)
        return self.session.exec(statement).first()

    def get_all_sessions_by_user(
        self,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[ChatSession]:
        """
        获取用户的所有会话列表（按更新时间倒序）

        Args:
            user_id: 用户 ID
            limit: 限制返回数量（可选）

        Returns:
            ChatSession 对象列表，按 updated_at 倒序排列
        """
        statement = select(ChatSession).where(
            ChatSession.user_id == user_id
        ).order_by(col(ChatSession.updated_at).desc())

        if limit:
            statement = statement.limit(limit)

        return self.session.exec(statement).all()

    def update_session_intent(
        self,
        session_id: int,
        intent: ChatIntent
    ) -> Optional[ChatSession]:
        """
        更新会话意图（Router 节点可能会修改意图）

        Args:
            session_id: 会话 ID
            intent: 新的会话意图

        Returns:
            更新后的 ChatSession 对象，不存在则返回 None
        """
        session = self.get_session_by_id(session_id)
        if session:
            session.intent = intent
            self.session.add(session)
            self.session.commit()
            self.session.refresh(session)
        return session

    def update_session_title(
        self,
        session_id: int,
        title: str
    ) -> Optional[ChatSession]:
        """
        更新会话标题

        Args:
            session_id: 会话 ID
            title: 新的会话标题

        Returns:
            更新后的 ChatSession 对象，不存在则返回 None
        """
        session = self.get_session_by_id(session_id)
        if session:
            session.title = title
            self.session.add(session)
            self.session.commit()
            self.session.refresh(session)
        return session

    def delete_session(self, session_id: int) -> bool:
        """
        删除会话（级联删除关联的消息）

        Args:
            session_id: 会话 ID

        Returns:
            删除成功返回 True，会话不存在返回 False
        """
        session = self.get_session_by_id(session_id)
        if session:
            # 先删除关联的消息
            self._delete_messages_by_session_id(session_id)
            # 再删除会话
            self.session.delete(session)
            self.session.commit()
            return True
        return False

    # ==================== ChatMessage 操作 ====================

    def create_message(
        self,
        session_id: int,
        role: MessageRole,
        content: str,
        thought_process: Optional[str] = None,
        related_artifact_id: Optional[int] = None,
        token_count: Optional[int] = None
    ) -> ChatMessage:
        """
        创建新消息

        Args:
            session_id: 会话 ID
            role: 消息角色枚举
            content: 消息内容
            thought_process: CoT 思维过程（可选）
            related_artifact_id: 关联交付物 ID（可选）
            token_count: token 数量（可选）

        Returns:
            创建的 ChatMessage 对象
        """
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            thought_process=thought_process,
            related_artifact_id=related_artifact_id,
            token_count=token_count
        )
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        return message

    def get_message_by_id(self, message_id: int) -> Optional[ChatMessage]:
        """
        根据 ID 获取消息

        Args:
            message_id: 消息 ID

        Returns:
            ChatMessage 对象，不存在则返回 None
        """
        return self.session.get(ChatMessage, message_id)

    def get_messages_by_session_id(
        self,
        session_id: int,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """
        获取会话的所有消息（按创建时间正序）

        Args:
            session_id: 会话 ID
            limit: 限制返回数量（可选）

        Returns:
            ChatMessage 对象列表，按 created_at 正序排列
        """
        statement = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(col(ChatMessage.created_at).asc())

        if limit:
            statement = statement.limit(limit)

        return self.session.exec(statement).all()

    def update_message_feedback(
        self,
        message_id: int,
        feedback: UserFeedback
    ) -> Optional[ChatMessage]:
        """
        更新消息的用户反馈

        Args:
            message_id: 消息 ID
            feedback: 用户反馈枚举

        Returns:
            更新后的 ChatMessage 对象，不存在则返回 None
        """
        message = self.get_message_by_id(message_id)
        if message:
            message.user_feedback = feedback
            self.session.add(message)
            self.session.commit()
            self.session.refresh(message)
        return message

    def _delete_messages_by_session_id(self, session_id: int) -> int:
        """
        删除会话的所有消息（内部方法）

        Args:
            session_id: 会话 ID

        Returns:
            删除的消息数量
        """
        statement = select(ChatMessage).where(ChatMessage.session_id == session_id)
        messages = self.session.exec(statement).all()
        count = len(messages)
        for message in messages:
            self.session.delete(message)
        return count
