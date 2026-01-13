"""
Pytest 测试配置
提供 Mock LLM、测试数据库等测试基础设施
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from sqlmodel import Session, create_engine
from unittest.mock import Mock, patch

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.init_db import create_tables
from app.models import (
    User, ProfileSection, ProfileSectionKey,
    Document, DocumentType,
    ChatSession, ChatIntent,
    ChatMessage, MessageRole,
    JobDescription,
    Artifact, ArtifactType
)


# ==================== 数据库 Fixtures ====================

@pytest.fixture(scope="function")
def test_db_engine():
    """
    创建测试用的内存数据库引擎
    每个测试函数都会获得一个全新的数据库
    """
    # 使用内存 SQLite 数据库
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    # 创建所有表
    create_tables(engine)

    yield engine

    # 测试结束后自动清理（内存数据库自动销毁）


@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """
    创建测试用的数据库会话
    """
    with Session(test_db_engine) as session:
        yield session


# ==================== Mock LLM Fixtures ====================

@pytest.fixture(scope="function")
def mock_llm():
    """
    Mock LLM 实例
    用于测试 Agent 节点，避免真实调用 LLM API
    """
    mock = Mock()
    # 配置默认返回值
    mock.invoke.return_value = Mock(content="Mock LLM response")
    return mock


@pytest.fixture(scope="function")
def mock_llm_with_structured_output():
    """
    Mock 带结构化输出的 LLM 实例
    用于测试 Scorer 节点
    """
    mock = Mock()

    def mock_with_structured_output(schema):
        """
        Mock with_structured_output 方法
        返回一个配置好的 Mock callable
        """
        mock_callable = Mock()
        # 模拟返回评分结果
        mock_callable.invoke.return_value = Mock(
            analysis_thought="Mock analysis",
            match_rating="High_Match",
            missing_skills=[],
            fit_reasons=["Good match"]
        )
        return mock_callable

    mock.with_structured_output = mock_with_structured_output
    return mock


@pytest.fixture(scope="function")
def mock_llm_factory(mock_llm):
    """
    Mock LLMFactory
    用于测试时替换真实的 LLM 工厂
    """
    with patch("app.agent.llm_factory.get_llm", return_value=mock_llm):
        yield mock_llm


# ==================== 测试数据 Fixtures ====================

@pytest.fixture(scope="function")
def test_user(test_db_session: Session) -> User:
    """
    创建测试用户
    """
    user = User(username="test_user", basic_info={"name": "测试用户", "city": "Beijing"})
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_profile_sections(test_db_session: Session, test_user: User) -> list[ProfileSection]:
    """
    创建测试画像切片（包含所有 7 种类型）
    """
    sections = []
    test_data = {
        ProfileSectionKey.SKILLS: {"programming": ["Python", "TypeScript"], "tools": ["Git", "Docker"]},
        ProfileSectionKey.WORK_EXPERIENCE: {"companies": ["ABC", "XYZ"], "total_years": 5},
        ProfileSectionKey.PROJECTS_SUMMARY: {"projects": ["E-commerce", "Blog"]},
        ProfileSectionKey.PROJECT_DETAILS: {"deep_dive": "详细项目经验..."},
        ProfileSectionKey.BEHAVIORAL_TRAITS: {"personality": "积极主动", "strengths": ["学习能力强"]},
        ProfileSectionKey.EDUCATION: {"degree": "本科", "major": "计算机科学"},
        ProfileSectionKey.SUMMARY: {"overview": "5 年 Python 开发经验"}
    }

    for section_key, content in test_data.items():
        section = ProfileSection(
            user_id=test_user.id,
            section_key=section_key,
            content=content
        )
        test_db_session.add(section)
        sections.append(section)

    test_db_session.commit()
    for section in sections:
        test_db_session.refresh(section)

    return sections


@pytest.fixture(scope="function")
def test_chat_session(test_db_session: Session, test_user: User) -> ChatSession:
    """
    创建测试会话
    """
    import uuid
    session = ChatSession(
        user_id=test_user.id,
        thread_id=str(uuid.uuid4()),
        intent=ChatIntent.RESUME_REFINE,
        title="测试简历优化会话",
        context_data={"test": True}
    )
    test_db_session.add(session)
    test_db_session.commit()
    test_db_session.refresh(session)
    return session


@pytest.fixture(scope="function")
def test_chat_messages(test_db_session: Session, test_chat_session: ChatSession) -> list[ChatMessage]:
    """
    创建测试消息（包含用户和助手消息）
    """
    messages = [
        ChatMessage(
            session_id=test_chat_session.id,
            role=MessageRole.USER,
            content="请帮我优化简历"
        ),
        ChatMessage(
            session_id=test_chat_session.id,
            role=MessageRole.ASSISTANT,
            content="好的，我来帮你优化简历",
            thought_process="用户需要简历优化服务"
        )
    ]

    for msg in messages:
        test_db_session.add(msg)

    test_db_session.commit()
    for msg in messages:
        test_db_session.refresh(msg)

    return messages


@pytest.fixture(scope="function")
def test_job_description(test_db_session: Session, test_user: User) -> JobDescription:
    """
    创建测试 JD
    """
    jd = JobDescription(
        user_id=test_user.id,
        title="Senior Python Developer",
        company="Tech Corp",
        raw_content="We are looking for a Senior Python Developer with 5+ years of experience...",
        parsed_tags={"skills": ["Python", "FastAPI", "SQL"], "experience": "5+ years"}
    )
    test_db_session.add(jd)
    test_db_session.commit()
    test_db_session.refresh(jd)
    return jd


@pytest.fixture(scope="function")
def test_artifact(test_db_session: Session, test_user: User, test_chat_session: ChatSession, test_job_description: JobDescription) -> Artifact:
    """
    创建测试交付物
    """
    artifact = Artifact(
        user_id=test_user.id,
        session_id=test_chat_session.id,
        jd_id=test_job_description.id,
        group_id=100,
        version=1,
        type=ArtifactType.RESUME,
        content={
            "personal_info": {"name": "Kevin", "email": "kevin@example.com"},
            "experience": [{"company": "ABC", "role": "Developer", "years": 3}]
        },
        meta_summary={"total_sections": 5, "word_count": 450}
    )
    test_db_session.add(artifact)
    test_db_session.commit()
    test_db_session.refresh(artifact)
    return artifact


# ==================== Repository Fixtures ====================

@pytest.fixture(scope="function")
def profile_repository(test_db_session: Session):
    """
    创建 ProfileRepository 实例
    """
    from app.repositories.profile_repository import ProfileRepository
    return ProfileRepository(test_db_session)


@pytest.fixture(scope="function")
def session_repository(test_db_session: Session):
    """
    创建 SessionRepository 实例
    """
    from app.repositories.session_repository import SessionRepository
    return SessionRepository(test_db_session)


@pytest.fixture(scope="function")
def artifact_repository(test_db_session: Session):
    """
    创建 ArtifactRepository 实例
    """
    from app.repositories.artifact_repository import ArtifactRepository
    return ArtifactRepository(test_db_session)


# ==================== Pytest 配置 ====================

def pytest_configure(config):
    """
    Pytest 初始化配置
    """
    # 标记测试分类
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
