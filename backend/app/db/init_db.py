"""
数据库初始化脚本
负责创建数据库表结构、默认用户和初始数据
"""

import os
from pathlib import Path
from typing import Optional

from sqlmodel import SQLModel, Session, create_engine, select

from app.models.user import User
from app.models.profile import ProfileSection, ProfileSectionKey
from app.models.observation import RawObservation, ObservationStatus, ObservationCategory
from app.models.document import Document, DocumentType
from app.models.chat import ChatSession, ChatIntent
from app.models.message import ChatMessage, MessageRole
from app.models.job import JobDescription
from app.models.artifact import Artifact, ArtifactType


def get_database_url() -> str:
    """
    获取数据库连接 URL
    优先使用环境变量，否则使用默认的 SQLite 文件
    """
    db_path = os.environ.get("DATABASE_PATH", "database.db")
    # 确保路径是绝对路径
    if not os.path.isabs(db_path):
        # 从项目根目录解析
        project_root = Path(__file__).parent.parent.parent
        db_path = str(project_root / db_path)
    return f"sqlite:///{db_path}"


def get_engine():
    """
    创建并返回数据库引擎
    """
    database_url = get_database_url()
    # SQLite 配置
    engine = create_engine(
        database_url,
        echo=False,  # 设置为 True 可查看 SQL 语句
        connect_args={"check_same_thread": False}  # SQLite 特有配置
    )
    return engine


def create_tables(engine) -> None:
    """
    创建所有数据库表
    SQLModel 会自动根据模型创建表结构
    """
    SQLModel.metadata.create_all(engine)
    print(f"Database tables created successfully at {get_database_url()}")


def create_default_user(session: Session) -> User:
    """
    创建默认用户 'me'
    如果用户已存在，则返回现有用户
    """
    # 检查是否已存在默认用户
    statement = select(User).where(User.username == "me")
    result = session.exec(statement).first()

    if result:
        print(f"Default user 'me' already exists (ID: {result.id})")
        return result

    # 创建默认用户
    default_user = User(username="me", basic_info={"name": "默认用户", "city": "Beijing"})
    session.add(default_user)
    session.commit()
    session.refresh(default_user)
    print(f"Created default user 'me' (ID: {default_user.id})")
    return default_user


def create_default_profile_sections(session: Session, user_id: int) -> None:
    """
    为用户创建 7 种默认的 profile_sections 切片（空内容）
    如果切片已存在，则跳过
    """
    # 定义所有 7 种切片类型
    all_section_keys = [
        ProfileSectionKey.SKILLS,
        ProfileSectionKey.WORK_EXPERIENCE,
        ProfileSectionKey.PROJECTS_SUMMARY,
        ProfileSectionKey.PROJECT_DETAILS,
        ProfileSectionKey.BEHAVIORAL_TRAITS,
        ProfileSectionKey.EDUCATION,
        ProfileSectionKey.SUMMARY
    ]

    created_count = 0
    for section_key in all_section_keys:
        # 检查是否已存在
        statement = select(ProfileSection).where(
            ProfileSection.user_id == user_id,
            ProfileSection.section_key == section_key
        )
        result = session.exec(statement).first()

        if result is None:
            # 创建空切片
            section = ProfileSection(
                user_id=user_id,
                section_key=section_key,
                content={}
            )
            session.add(section)
            created_count += 1

    if created_count > 0:
        session.commit()
        print(f"Created {created_count} default profile_sections for user {user_id}")
    else:
        print(f"Profile sections already exist for user {user_id}")


def create_default_chat_session(session: Session, user_id: int) -> ChatSession:
    """
    创建第一个默认 chat_sessions
    如果会话已存在，则返回现有会话
    """
    # 检查是否已存在会话
    statement = select(ChatSession).where(ChatSession.user_id == user_id)
    result = session.exec(statement).first()

    if result:
        print(f"Chat session already exists (ID: {result.id}, thread_id: {result.thread_id})")
        return result

    # 创建第一个会话
    import uuid
    default_session = ChatSession(
        user_id=user_id,
        thread_id=str(uuid.uuid4()),
        intent=ChatIntent.ONBOARDING,
        title="欢迎使用智能职业顾问",
        context_data={"initialized": True}
    )
    session.add(default_session)
    session.commit()
    session.refresh(default_session)
    print(f"Created default chat session (ID: {default_session.id}, thread_id: {default_session.thread_id})")
    return default_session


def create_default_data(session: Session) -> None:
    """
    创建所有默认数据
    包括默认用户、画像切片和第一个会话
    """
    print("\n=== Creating default data ===")

    # 创建默认用户
    default_user = create_default_user(session)

    # 创建默认画像切片
    create_default_profile_sections(session, default_user.id)

    # 创建默认会话
    create_default_chat_session(session, default_user.id)

    print("=== Default data creation completed ===\n")


def init_db() -> None:
    """
    完整的数据库初始化流程
    1. 创建数据库引擎
    2. 创建所有表结构
    3. 创建默认数据
    """
    print("\n=== Initializing database ===")

    # 创建引擎
    engine = get_engine()

    # 创建表结构
    create_tables(engine)

    # 创建默认数据
    with Session(engine) as session:
        create_default_data(session)

    print("=== Database initialization completed ===\n")


if __name__ == "__main__":
    # 直接运行此脚本时，执行数据库初始化
    init_db()
