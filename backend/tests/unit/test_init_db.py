"""
数据库初始化单元测试
验证数据库表的创建、默认用户和初始数据的生成
"""

import pytest
from sqlmodel import Session, create_engine, select
from unittest.mock import patch

from app.db.init_db import create_tables, create_default_user, create_default_profile_sections, create_default_chat_session, create_default_data, init_db
from app.models.user import User
from app.models.profile import ProfileSection, ProfileSectionKey
from app.models.chat import ChatSession, ChatIntent


class TestDatabaseInit:
    """测试数据库初始化"""

    def test_create_tables(self):
        """测试创建所有表"""
        # 使用内存数据库
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

        create_tables(engine)

        # 验证表已创建（尝试查询应该不会报错）
        with Session(engine) as session:
            # 尝试查询用户表
            statement = select(User)
            result = session.exec(statement).all()
            assert isinstance(result, list)

    def test_create_default_user(self):
        """测试创建默认用户"""
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        create_tables(engine)

        with Session(engine) as session:
            user = create_default_user(session)

            assert user is not None
            assert user.username == "me"
            assert user.id is not None

            # 再次调用应该返回已存在的用户
            user2 = create_default_user(session)
            assert user2.id == user.id

    def test_create_default_profile_sections(self):
        """测试创建默认画像切片"""
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        create_tables(engine)

        with Session(engine) as session:
            # 先创建用户
            user = create_default_user(session)

            # 创建切片
            create_default_profile_sections(session, user.id)

            # 验证 7 种切片都已创建
            statement = select(ProfileSection).where(ProfileSection.user_id == user.id)
            sections = session.exec(statement).all()

            assert len(sections) == 7

            # 验证所有 7 种类型都存在
            section_keys = {s.section_key for s in sections}
            expected_keys = {
                ProfileSectionKey.SKILLS,
                ProfileSectionKey.WORK_EXPERIENCE,
                ProfileSectionKey.PROJECTS_SUMMARY,
                ProfileSectionKey.PROJECT_DETAILS,
                ProfileSectionKey.BEHAVIORAL_TRAITS,
                ProfileSectionKey.EDUCATION,
                ProfileSectionKey.SUMMARY
            }
            assert section_keys == expected_keys

    def test_create_default_chat_session(self):
        """测试创建默认会话"""
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        create_tables(engine)

        with Session(engine) as session:
            # 先创建用户
            user = create_default_user(session)

            # 创建会话
            session_obj = create_default_chat_session(session, user.id)

            assert session_obj is not None
            assert session_obj.user_id == user.id
            assert session_obj.intent == ChatIntent.ONBOARDING
            assert session_obj.thread_id is not None

            # 再次调用应该返回已存在的会话
            session_obj2 = create_default_chat_session(session, user.id)
            assert session_obj2.id == session_obj.id

    def test_create_default_data(self):
        """测试创建所有默认数据"""
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        create_tables(engine)

        with Session(engine) as session:
            create_default_data(session)

            # 验证用户已创建
            user_statement = select(User).where(User.username == "me")
            user = session.exec(user_statement).first()
            assert user is not None

            # 验证切片已创建
            section_statement = select(ProfileSection).where(ProfileSection.user_id == user.id)
            sections = session.exec(section_statement).all()
            assert len(sections) == 7

            # 验证会话已创建
            session_statement = select(ChatSession).where(ChatSession.user_id == user.id)
            chat_session = session.exec(session_statement).first()
            assert chat_session is not None

    def test_init_db_complete_flow(self):
        """测试完整的初始化流程"""
        # Mock get_engine to use in-memory database
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

        with patch("app.db.init_db.get_engine", return_value=engine):
            # 执行完整初始化
            init_db()

            # 验证数据已正确初始化
            with Session(engine) as session:
                # 检查用户
                user_statement = select(User).where(User.username == "me")
                user = session.exec(user_statement).first()
                assert user is not None

                # 检查切片
                section_statement = select(ProfileSection).where(ProfileSection.user_id == user.id)
                sections = session.exec(section_statement).all()
                assert len(sections) == 7

                # 检查会话
                session_statement = select(ChatSession).where(ChatSession.user_id == user.id)
                chat_session = session.exec(session_statement).first()
                assert chat_session is not None
