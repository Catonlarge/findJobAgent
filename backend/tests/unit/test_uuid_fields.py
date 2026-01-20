"""
V7.2 UUID 字段单元测试

测试新增的 UUID 字段：
1. ChatMessage.msg_uuid
2. ChatSession.session_uuid
3. ProfileSection.tags
4. RawObservation.source_msg_uuid（上一轮已测试）
"""

import pytest
import uuid
from datetime import datetime
from sqlmodel import Session, create_engine

from app.models.chat import ChatSession, ChatIntent
from app.models.message import ChatMessage, MessageRole
from app.models.profile import ProfileSection, ProfileSectionKey
from app.models.observation import RawObservation, ObservationCategory, ObservationStatus
from app.db.init_db import get_engine


class TestChatSessionUUID:
    """测试 ChatSession.session_uuid 字段"""

    def test_session_uuid_field_exists(self):
        """测试：session_uuid 字段存在"""
        assert hasattr(ChatSession, 'session_uuid')
        field = ChatSession.session_uuid
        # SQLModel 使用 AutoString 类型
        assert field.property.columns[0].type.__class__.__name__ in ['String', 'TEXT', 'VARCHAR', 'AutoString']

    def test_create_session_with_uuid(self):
        """测试：创建会话时可以设置 UUID"""
        test_uuid = str(uuid.uuid4())
        session = ChatSession(
            user_id=1,
            session_uuid=test_uuid,
            thread_id="thread-123",
            intent=ChatIntent.GENERAL_CHAT,
            title="测试会话"
        )

        assert session.session_uuid == test_uuid
        assert session.session_uuid is not None

    def test_session_uuid_is_unique(self):
        """测试：session_uuid 应该唯一（由数据库约束保证）"""
        # 注意：唯一性约束由数据库 UNIQUE INDEX 保证
        # 这里只测试 Python 层面的逻辑
        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())

        session1 = ChatSession(
            user_id=1,
            session_uuid=uuid1,
            thread_id="thread-1",
            intent=ChatIntent.GENERAL_CHAT,
            title="会话1"
        )
        session2 = ChatSession(
            user_id=1,
            session_uuid=uuid2,
            thread_id="thread-2",
            intent=ChatIntent.GENERAL_CHAT,
            title="会话2"
        )

        assert session1.session_uuid != session2.session_uuid


class TestChatMessageUUID:
    """测试 ChatMessage.msg_uuid 字段"""

    def test_msg_uuid_field_exists(self):
        """测试：msg_uuid 字段存在"""
        assert hasattr(ChatMessage, 'msg_uuid')
        field = ChatMessage.msg_uuid
        # SQLModel 使用 AutoString 类型
        assert field.property.columns[0].type.__class__.__name__ in ['String', 'TEXT', 'VARCHAR', 'AutoString']

    def test_create_message_with_uuid(self):
        """测试：创建消息时可以设置 UUID"""
        test_uuid = str(uuid.uuid4())
        message = ChatMessage(
            session_id=1,
            msg_uuid=test_uuid,
            role=MessageRole.USER,
            content="测试消息"
        )

        assert message.msg_uuid == test_uuid
        assert message.msg_uuid is not None

    def test_msg_uuid_supports_lineage_tracking(self):
        """测试：msg_uuid 支持血缘追踪"""
        msg_uuid = str(uuid.uuid4())

        # 创建原始消息
        user_msg = ChatMessage(
            session_id=1,
            msg_uuid=msg_uuid,
            role=MessageRole.USER,
            content="我会 Python"
        )

        # 创建关联的观察（使用相同的 UUID）
        observation = RawObservation(
            user_id=1,
            source_msg_uuid=msg_uuid,  # 关联到消息
            category=ObservationCategory.SKILL,
            fact_content="用户会 Python",
            confidence=80,
            status=ObservationStatus.PENDING
        )

        assert user_msg.msg_uuid == observation.source_msg_uuid


class TestProfileSectionTags:
    """测试 ProfileSection.tags 字段"""

    def test_tags_field_exists(self):
        """测试：tags 字段存在"""
        assert hasattr(ProfileSection, 'tags')

    def test_create_section_with_tags(self):
        """测试：创建切片时可以设置标签"""
        section = ProfileSection(
            user_id=1,
            section_key=ProfileSectionKey.SKILLS,
            content={"skills": ["Python", "FastAPI"]},
            tags={"languages": ["Python"], "frameworks": ["FastAPI"]}
        )

        assert section.tags is not None
        assert "languages" in section.tags
        assert section.tags["languages"] == ["Python"]

    def test_tags_default_to_none(self):
        """测试：tags 默认为 None"""
        section = ProfileSection(
            user_id=1,
            section_key=ProfileSectionKey.SKILLS,
            content={}
        )

        assert section.tags is None


class TestDatabaseIntegration:
    """集成测试：验证 UUID 字段在数据库中的行为"""

    @pytest.fixture
    def engine(self):
        """创建临时内存数据库"""
        engine = create_engine("sqlite:///:memory:")
        return engine

    @pytest.fixture
    def session(self, engine):
        """创建数据库会话"""
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            yield session

    def test_save_and_load_session_with_uuid(self, session):
        """测试：保存和加载带 UUID 的会话"""
        test_uuid = str(uuid.uuid4())

        # 创建并保存会话
        new_session = ChatSession(
            user_id=1,
            session_uuid=test_uuid,
            thread_id="thread-123",
            intent=ChatIntent.GENERAL_CHAT,
            title="测试会话"
        )
        session.add(new_session)
        session.commit()
        session.refresh(new_session)

        # 加载会话
        from sqlmodel import select
        statement = select(ChatSession).where(ChatSession.session_uuid == test_uuid)
        loaded_session = session.exec(statement).first()

        assert loaded_session is not None
        assert loaded_session.session_uuid == test_uuid
        assert loaded_session.title == "测试会话"

    def test_save_and_load_message_with_uuid(self, session):
        """测试：保存和加载带 UUID 的消息"""
        test_uuid = str(uuid.uuid4())

        # 创建消息
        message = ChatMessage(
            session_id=1,
            msg_uuid=test_uuid,
            role=MessageRole.USER,
            content="测试消息"
        )
        session.add(message)
        session.commit()
        session.refresh(message)

        # 加载消息
        from sqlmodel import select
        statement = select(ChatMessage).where(ChatMessage.msg_uuid == test_uuid)
        loaded_message = session.exec(statement).first()

        assert loaded_message is not None
        assert loaded_message.msg_uuid == test_uuid
        assert loaded_message.content == "测试消息"

    def test_observation_message_uuid_foreign_key(self, session):
        """测试：观察表通过 UUID 关联到消息"""
        msg_uuid = str(uuid.uuid4())

        # 创建消息
        message = ChatMessage(
            session_id=1,
            msg_uuid=msg_uuid,
            role=MessageRole.USER,
            content="我会 Python"
        )
        session.add(message)
        session.commit()

        # 创建关联的观察
        observation = RawObservation(
            user_id=1,
            source_msg_uuid=msg_uuid,
            category=ObservationCategory.SKILL,
            fact_content="用户会 Python",
            confidence=80,
            status=ObservationStatus.PENDING
        )
        session.add(observation)
        session.commit()

        # 验证关联
        from sqlmodel import select
        statement = select(RawObservation).where(RawObservation.source_msg_uuid == msg_uuid)
        loaded_obs = session.exec(statement).first()

        assert loaded_obs is not None
        assert loaded_obs.source_msg_uuid == msg_uuid
        assert loaded_obs.fact_content == "用户会 Python"


class TestMessageUtils:
    """测试 message_utils 工具函数"""

    def test_create_human_message_generates_uuid(self):
        """测试：create_human_message 自动生成 UUID"""
        from app.agent.sharednodes.message_utils import create_human_message

        msg = create_human_message("你好")

        assert msg.id is not None
        assert len(msg.id) > 0
        assert msg.content == "你好"

    def test_create_human_message_with_custom_uuid(self):
        """测试：create_human_message 支持自定义 UUID"""
        from app.agent.sharednodes.message_utils import create_human_message

        custom_uuid = "custom-uuid-123"
        msg = create_human_message("你好", msg_uuid=custom_uuid)

        assert msg.id == custom_uuid

    def test_create_ai_message_generates_uuid(self):
        """测试：create_ai_message 自动生成 UUID"""
        from app.agent.sharednodes.message_utils import create_ai_message

        msg = create_ai_message("你好，我是 AI")

        assert msg.id is not None
        assert msg.content == "你好，我是 AI"
