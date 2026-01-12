"""
数据库模型单元测试
验证所有7个表模型的定义是否正确
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List

# 导入所有模型和枚举
import sys
import os

# 添加 backend 目录到路径，以便导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.models.user import User
from app.models.profile import ProfileSection, ProfileSectionKey
from app.models.document import Document, DocumentType
from app.models.chat import ChatSession, ChatIntent
from app.models.message import ChatMessage, MessageRole, UserFeedback
from app.models.job import JobDescription
from app.models.artifact import Artifact, ArtifactType, MatchRating

class TestUserModel:
    """测试用户模型"""

    def test_user_creation(self):
        """测试创建用户实例"""
        user = User(
            username="test_user",
            basic_info={"name": "Kevin", "city": "Beijing"}
        )

        assert user.username == "test_user"
        assert user.basic_info == {"name": "Kevin", "city": "Beijing"}
        assert user.id is None  # 尚未保存到数据库
        assert isinstance(user.created_at, datetime)

    def test_user_minimal_creation(self):
        """测试最小化创建用户（只有必需字段）"""
        user = User(username="minimal_user")

        assert user.username == "minimal_user"
        assert user.basic_info == {}  # 默认值
        assert isinstance(user.created_at, datetime)

class TestProfileSectionModel:
    """测试画像切片模型"""

    def test_profile_section_creation(self):
        """测试创建画像切片"""
        section = ProfileSection(
            user_id=1,
            section_key=ProfileSectionKey.SKILLS,
            content={"programming": ["Python", "TypeScript"], "tools": ["Git", "Docker"]}
        )

        assert section.user_id == 1
        assert section.section_key == ProfileSectionKey.SKILLS
        assert "programming" in section.content
        assert isinstance(section.updated_at, datetime)

    def test_all_profile_section_keys(self):
        """测试所有画像切片枚举值"""
        expected_keys = [
            ProfileSectionKey.SKILLS,
            ProfileSectionKey.WORK_EXPERIENCE,
            ProfileSectionKey.PROJECTS_SUMMARY,
            ProfileSectionKey.PROJECT_DETAILS,
            ProfileSectionKey.BEHAVIORAL_TRAITS,
            ProfileSectionKey.EDUCATION,
            ProfileSectionKey.SUMMARY
        ]

        for key in expected_keys:
            section = ProfileSection(
                user_id=1,
                section_key=key,
                content={}
            )
            assert section.section_key == key

class TestDocumentModel:
    """测试文档模型"""

    def test_document_creation(self):
        """测试创建文档"""
        doc = Document(
            user_id=1,
            type=DocumentType.RAW_RESUME,
            content="5 years Python experience..."
        )

        assert doc.user_id == 1
        assert doc.type == DocumentType.RAW_RESUME
        assert doc.content == "5 years Python experience..."
        assert isinstance(doc.created_at, datetime)
        assert doc.created_at.tzinfo is None  # UTC 时间

    def test_all_document_types(self):
        """测试所有文档类型"""
        types = [
            DocumentType.RAW_RESUME,
            DocumentType.JD_TEXT,
            DocumentType.BIOGRAPHY
        ]

        for doc_type in types:
            doc = Document(
                user_id=1,
                type=doc_type,
                content="test content"
            )
            assert doc.type == doc_type

class TestChatSessionModel:
    """测试会话模型"""

    def test_chat_session_creation(self):
        """测试创建会话"""
        session = ChatSession(
            user_id=1,
            thread_id="thread_123",
            intent=ChatIntent.RESUME_REFINE,
            title="优化我的简历",
            context_data={"persona": "professional_reviewer"}
        )

        assert session.user_id == 1
        assert session.thread_id == "thread_123"
        assert session.intent == ChatIntent.RESUME_REFINE
        assert session.title == "优化我的简历"
        assert session.context_data["persona"] == "professional_reviewer"
        assert isinstance(session.updated_at, datetime)

    def test_all_chat_intents(self):
        """测试所有会话意图"""
        intents = [
            ChatIntent.RESUME_REFINE,
            ChatIntent.INTERVIEW_PREP,
            ChatIntent.GENERAL_CHAT,
            ChatIntent.ONBOARDING
        ]

        for intent in intents:
            session = ChatSession(
                user_id=1,
                thread_id=f"thread_{intent}",
                intent=intent,
                title=f"Test {intent}"
            )
            assert session.intent == intent

class TestChatMessageModel:
    """测试聊天消息模型"""

    def test_chat_message_creation(self):
        """测试创建聊天消息"""
        message = ChatMessage(
            session_id=1,
            role=MessageRole.ASSISTANT,
            thought_process="分析用户技能...",
            content="根据你的技能，建议突出 Python 和 FastAPI 经验",
            token_count=150
        )

        assert message.session_id == 1
        assert message.role == MessageRole.ASSISTANT
        assert message.thought_process == "分析用户技能..."
        assert message.content == "根据你的技能，建议突出 Python 和 FastAPI 经验"
        assert message.token_count == 150
        assert message.related_artifact_id is None  # 可选字段
        assert message.user_feedback is None  # 可选字段

    def test_chat_message_with_artifact(self):
        """测试带有关联交付物的消息"""
        message = ChatMessage(
            session_id=1,
            role=MessageRole.ASSISTANT,
            content="已生成简历分析报告",
            related_artifact_id=5
        )

        assert message.related_artifact_id == 5

    def test_user_feedback(self):
        """测试用户反馈枚举"""
        feedbacks = [UserFeedback.LIKE, UserFeedback.DISLIKE, UserFeedback.CORRECTION]

        for feedback in feedbacks:
            message = ChatMessage(
                session_id=1,
                role=MessageRole.USER,
                content="这个建议很好",
                user_feedback=feedback
            )
            assert message.user_feedback == feedback

class TestJobDescriptionModel:
    """测试职位描述模型"""

    def test_job_description_creation(self):
        """测试创建职位描述"""
        jd = JobDescription(
            user_id=1,
            title="Senior Python Developer",
            company="Tech Corp",
            raw_content="5+ years Python experience required...",
            parsed_tags={"skills": ["Python", "FastAPI"], "experience": "5+ years"}
        )

        assert jd.user_id == 1
        assert jd.title == "Senior Python Developer"
        assert jd.company == "Tech Corp"
        assert "Python" in jd.parsed_tags["skills"]
        assert isinstance(jd.created_at, datetime)

    def test_job_description_minimal(self):
        """测试最小化职位描述（只有必需字段）"""
        jd = JobDescription(
            user_id=1,
            title="Python Developer",
            raw_content="Python experience required"
        )

        assert jd.company is None
        assert jd.parsed_tags == {}

class TestArtifactModel:
    """测试交付物模型"""

    def test_artifact_creation(self):
        """测试创建交付物"""
        artifact = Artifact(
            user_id=1,
            session_id=2,
            jd_id=3,
            group_id=100,
            version=1,
            type=ArtifactType.RESUME,
            content={
                "personal_info": {"name": "Kevin", "email": "kevin@example.com"},
                "experience": [{"company": "ABC", "role": "Developer"}]
            },
            meta_summary={"total_sections": 5, "word_count": 450}
        )

        assert artifact.user_id == 1
        assert artifact.session_id == 2
        assert artifact.jd_id == 3
        assert artifact.group_id == 100
        assert artifact.version == 1
        assert artifact.type == ArtifactType.RESUME
        assert artifact.schema_version == 1  # 默认值
        assert artifact.meta_summary["total_sections"] == 5

    def test_artifact_version_uniqueness(self):
        """测试版本号和组合唯一性"""
        # 理论上 group_id 和 version 应该是唯一的组合
        # 这里只测试模型层面，数据库层面的唯一性约束在迁移时创建
        artifact1 = Artifact(
            user_id=1,
            group_id=100,
            version=1,
            type=ArtifactType.RESUME,
            content={}
        )

        artifact2 = Artifact(
            user_id=1,
            group_id=100,
            version=2,
            type=ArtifactType.RESUME,
            content={}
        )

        assert artifact1.group_id == artifact2.group_id
        assert artifact1.version != artifact2.version

    def test_all_artifact_types(self):
        """测试所有交付物类型"""
        types = [
            ArtifactType.RESUME,
            ArtifactType.ANALYSIS_REPORT,
            ArtifactType.COVER_LETTER
        ]

        for artifact_type in types:
            artifact = Artifact(
                user_id=1,
                group_id=200,
                version=1,
                type=artifact_type,
                content={}
            )
            assert artifact.type == artifact_type

    def test_match_rating_enum(self):
        """测试匹配度评级枚举"""
        ratings = [
            MatchRating.PERFECT_MATCH,
            MatchRating.HIGH_MATCH,
            MatchRating.MEDIUM_MATCH,
            MatchRating.LOW_MATCH
        ]

        # 这些可以用于 analysis_report 类型的 content 中
        for rating in ratings:
            artifact = Artifact(
                user_id=1,
                group_id=300,
                version=1,
                type=ArtifactType.ANALYSIS_REPORT,
                content={"match_rating": rating, "analysis": "Detailed analysis"}
            )
            assert artifact.content["match_rating"] == rating

class TestModelRelationships:
    """测试模型间的外键关系（逻辑层面）"""

    def test_user_to_profile_section_relationship(self):
        """测试用户到画像切片的逻辑关系"""
        user_id = 1

        # 模拟多个画像切片
        skill_section = ProfileSection(
            user_id=user_id,
            section_key=ProfileSectionKey.SKILLS,
            content={"Python": "Expert"}
        )

        experience_section = ProfileSection(
            user_id=user_id,
            section_key=ProfileSectionKey.WORK_EXPERIENCE,
            content={"companies": ["A", "B"]}
        )

        assert skill_section.user_id == user_id
        assert experience_section.user_id == user_id

    def test_session_to_message_relationship(self):
        """测试会话到消息的逻辑关系"""
        session_id = 10

        # 模拟会话中的多条消息
        user_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.USER,
            content="Hello"
        )

        assistant_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content="Hi there!"
        )

        assert user_message.session_id == session_id
        assert assistant_message.session_id == session_id
        assert user_message.role != assistant_message.role

    def test_jd_to_artifact_relationship(self):
        """测试 JD 到交付物的逻辑关系"""
        jd_id = 5

        analysis_artifact = Artifact(
            user_id=1,
            jd_id=jd_id,
            group_id=400,
            version=1,
            type=ArtifactType.ANALYSIS_REPORT,
            content={"analysis": "JD matching analysis"}
        )

        assert analysis_artifact.jd_id == jd_id

if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v"])
