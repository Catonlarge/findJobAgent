"""
Repository 单元测试
验证 ProfileRepository、SessionRepository 和 ArtifactRepository 的 CRUD 操作
"""

import pytest

from app.models.profile import ProfileSectionKey
from app.models.chat import ChatIntent
from app.models.message import MessageRole, UserFeedback
from app.models.artifact import ArtifactType


class TestProfileRepository:
    """测试 ProfileRepository"""

    def test_create_profile_section(self, profile_repository, test_user):
        """测试创建画像切片"""
        section = profile_repository.create(
            user_id=test_user.id,
            section_key=ProfileSectionKey.SKILLS,
            content={"programming": ["Python", "Go"], "tools": ["Git"]}
        )

        assert section.id is not None
        assert section.user_id == test_user.id
        assert section.section_key == ProfileSectionKey.SKILLS
        assert "Python" in section.content["programming"]

    def test_get_by_user_and_key(self, profile_repository, test_user):
        """测试根据用户和类型获取切片"""
        # 先创建切片
        profile_repository.create(
            user_id=test_user.id,
            section_key=ProfileSectionKey.EDUCATION,
            content={"degree": "本科", "major": "计算机"}
        )

        # 查询切片
        section = profile_repository.get_by_user_and_key(
            user_id=test_user.id,
            section_key=ProfileSectionKey.EDUCATION
        )

        assert section is not None
        assert section.content["degree"] == "本科"

    def test_get_all_by_user(self, profile_repository, test_user, test_profile_sections):
        """测试获取用户的所有切片"""
        sections = profile_repository.get_all_by_user(test_user.id)

        assert len(sections) == 7  # 应该有 7 种切片类型

    def test_get_user_profile_dict(self, profile_repository, test_user, test_profile_sections):
        """测试获取用户画像字典"""
        profile_dict = profile_repository.get_user_profile_dict(test_user.id)

        assert isinstance(profile_dict, dict)
        assert "skills" in profile_dict
        assert "education" in profile_dict
        assert profile_dict["skills"]["programming"] == ["Python", "TypeScript"]

    def test_update_by_user_and_key(self, profile_repository, test_user):
        """测试更新切片内容"""
        # 先创建切片
        profile_repository.create(
            user_id=test_user.id,
            section_key=ProfileSectionKey.SKILLS,
            content={"programming": ["Python"]}
        )

        # 更新切片
        updated_section = profile_repository.update_by_user_and_key(
            user_id=test_user.id,
            section_key=ProfileSectionKey.SKILLS,
            content={"programming": ["Python", "TypeScript", "Go"]}
        )

        assert updated_section is not None
        assert len(updated_section.content["programming"]) == 3

    def test_upsert_multiple(self, profile_repository, test_user):
        """测试批量创建或更新切片"""
        sections_data = {
            ProfileSectionKey.SKILLS: {"languages": ["Python"]},
            ProfileSectionKey.EDUCATION: {"degree": "硕士"}
        }

        result = profile_repository.upsert_multiple(test_user.id, sections_data)

        assert len(result) == 2

    def test_delete_profile_section(self, profile_repository, test_user):
        """测试删除切片"""
        # 先创建切片
        section = profile_repository.create(
            user_id=test_user.id,
            section_key=ProfileSectionKey.BEHAVIORAL_TRAITS,
            content={"personality": "乐观"}
        )

        # 删除切片
        success = profile_repository.delete(section.id)

        assert success is True
        # 验证已删除
        deleted_section = profile_repository.get_by_id(section.id)
        assert deleted_section is None


class TestSessionRepository:
    """测试 SessionRepository"""

    def test_create_session(self, session_repository, test_user):
        """测试创建会话"""
        import uuid
        session = session_repository.create_session(
            user_id=test_user.id,
            session_uuid=str(uuid.uuid4()),
            intent=ChatIntent.RESUME_REFINE,
            title="优化简历"
        )

        assert session.id is not None
        assert session.user_id == test_user.id
        assert session.intent == ChatIntent.RESUME_REFINE

    def test_get_session_by_thread_id(self, session_repository, test_chat_session):
        """测试根据 thread_id 获取会话"""
        session = session_repository.get_session_by_thread_id(test_chat_session.thread_id)

        assert session is not None
        assert session.id == test_chat_session.id

    def test_get_all_sessions_by_user(self, session_repository, test_user):
        """测试获取用户的所有会话"""
        # 创建多个会话
        for i in range(3):
            import uuid
            session_repository.create_session(
                user_id=test_user.id,
                session_uuid=str(uuid.uuid4()),
                intent=ChatIntent.GENERAL_CHAT,
                title=f"会话 {i+1}"
            )

        sessions = session_repository.get_all_sessions_by_user(test_user.id)

        assert len(sessions) >= 3

    def test_create_message(self, session_repository, test_chat_session):
        """测试创建消息"""
        message = session_repository.create_message(
            session_id=test_chat_session.id,
            role=MessageRole.USER,
            content="你好"
        )

        assert message.id is not None
        assert message.session_id == test_chat_session.id
        assert message.role == MessageRole.USER

    def test_create_message_with_uuid(self, session_repository, test_chat_session):
        """测试创建带 msg_uuid 的消息"""
        import uuid
        msg_uuid = str(uuid.uuid4())
        message = session_repository.create_message(
            session_id=test_chat_session.id,
            role=MessageRole.USER,
            content="我会 Python",
            msg_uuid=msg_uuid
        )

        assert message.id is not None
        assert message.session_id == test_chat_session.id
        assert message.role == MessageRole.USER
        assert message.msg_uuid == msg_uuid

    def test_create_message_without_uuid(self, session_repository, test_chat_session):
        """测试创建不带 msg_uuid 的消息（向后兼容）"""
        message = session_repository.create_message(
            session_id=test_chat_session.id,
            role=MessageRole.ASSISTANT,
            content="你好！有什么可以帮助你的？"
        )

        assert message.id is not None
        assert message.msg_uuid is None

    def test_get_messages_by_session_id(self, session_repository, test_chat_session, test_chat_messages):
        """测试获取会话的所有消息"""
        messages = session_repository.get_messages_by_session_id(test_chat_session.id)

        assert len(messages) == 2  # 我们创建了 2 条消息

    def test_update_message_feedback(self, session_repository, test_chat_session):
        """测试更新消息反馈"""
        # 先创建消息
        message = session_repository.create_message(
            session_id=test_chat_session.id,
            role=MessageRole.ASSISTANT,
            content="建议..."
        )

        # 更新反馈
        updated_message = session_repository.update_message_feedback(
            message_id=message.id,
            feedback=UserFeedback.LIKE
        )

        assert updated_message is not None
        assert updated_message.user_feedback == UserFeedback.LIKE

    def test_delete_session(self, session_repository, test_chat_session):
        """测试删除会话"""
        session_id = test_chat_session.id

        # 删除会话
        success = session_repository.delete_session(session_id)

        assert success is True
        # 验证已删除
        deleted_session = session_repository.get_session_by_id(session_id)
        assert deleted_session is None


class TestArtifactRepository:
    """测试 ArtifactRepository"""

    def test_create_artifact(self, artifact_repository, test_user, test_chat_session, test_job_description):
        """测试创建交付物"""
        artifact = artifact_repository.create(
            user_id=test_user.id,
            group_id=100,
            version=1,
            artifact_type=ArtifactType.RESUME,
            content={"name": "Kevin", "skills": ["Python"]},
            session_id=test_chat_session.id,
            jd_id=test_job_description.id
        )

        assert artifact.id is not None
        assert artifact.group_id == 100
        assert artifact.version == 1

    def test_get_by_group(self, artifact_repository, test_user, test_chat_session, test_job_description):
        """测试获取版本组的所有版本"""
        # 创建同一组的多个版本
        for version in range(1, 4):
            artifact_repository.create(
                user_id=test_user.id,
                group_id=200,
                version=version,
                artifact_type=ArtifactType.ANALYSIS_REPORT,
                content={"version": version},
                session_id=test_chat_session.id,
                jd_id=test_job_description.id
            )

        artifacts = artifact_repository.get_by_group(200)

        assert len(artifacts) == 3
        # 验证按版本倒序排列
        assert artifacts[0].version == 3
        assert artifacts[2].version == 1

    def test_get_latest_by_group(self, artifact_repository, test_user, test_chat_session, test_job_description):
        """测试获取版本组的最新版本"""
        # 创建多个版本
        for version in range(1, 4):
            artifact_repository.create(
                user_id=test_user.id,
                group_id=300,
                version=version,
                artifact_type=ArtifactType.RESUME,
                content={},
                session_id=test_chat_session.id,
                jd_id=test_job_description.id
            )

        latest = artifact_repository.get_latest_by_group(300)

        assert latest is not None
        assert latest.version == 3

    def test_create_new_version(self, artifact_repository, test_user, test_chat_session, test_job_description):
        """测试自动创建新版本"""
        # 创建第一个版本
        v1 = artifact_repository.create_new_version(
            user_id=test_user.id,
            artifact_type=ArtifactType.RESUME,
            content={"version": 1},
            session_id=test_chat_session.id,
            jd_id=test_job_description.id
        )

        # 创建第二个版本（应该自动递增版本号）
        v2 = artifact_repository.create_new_version(
            user_id=test_user.id,
            artifact_type=ArtifactType.RESUME,
            content={"version": 2},
            session_id=test_chat_session.id,
            jd_id=test_job_description.id
        )

        assert v1.group_id == v2.group_id  # 同一组
        assert v1.version == 1
        assert v2.version == 2

    def test_get_by_session(self, artifact_repository, test_artifact):
        """测试获取会话的所有交付物"""
        artifacts = artifact_repository.get_by_session(test_artifact.session_id)

        assert len(artifacts) >= 1

    def test_get_by_jd(self, artifact_repository, test_artifact):
        """测试获取 JD 的所有交付物"""
        artifacts = artifact_repository.get_by_jd(test_artifact.jd_id)

        assert len(artifacts) >= 1

    def test_update_content(self, artifact_repository, test_artifact):
        """测试更新交付物内容"""
        updated = artifact_repository.update_content(
            artifact_id=test_artifact.id,
            content={"updated": True},
            meta_summary={"version": 2}
        )

        assert updated is not None
        assert updated.content["updated"] is True
        assert updated.meta_summary["version"] == 2

    def test_delete_artifact(self, artifact_repository, test_user, test_chat_session, test_job_description):
        """测试删除交付物"""
        artifact = artifact_repository.create(
            user_id=test_user.id,
            group_id=500,
            version=1,
            artifact_type=ArtifactType.COVER_LETTER,
            content={},
            session_id=test_chat_session.id,
            jd_id=test_job_description.id
        )

        success = artifact_repository.delete(artifact.id)

        assert success is True
