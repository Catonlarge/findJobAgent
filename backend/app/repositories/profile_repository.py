"""
画像切片 Repository
提供 profile_sections 的增删改查操作
"""

from typing import List, Optional, Dict, Any

from sqlmodel import Session, select, col

from app.models.profile import ProfileSection, ProfileSectionKey


class ProfileRepository:
    """
    画像切片数据访问对象
    封装所有与 profile_sections 表相关的数据库操作
    """

    def __init__(self, session: Session):
        """
        初始化 Repository

        Args:
            session: SQLModel 数据库会话
        """
        self.session = session

    def create(
        self,
        user_id: int,
        section_key: ProfileSectionKey,
        content: Dict[str, Any]
    ) -> ProfileSection:
        """
        创建新的画像切片

        Args:
            user_id: 用户 ID
            section_key: 切片类型枚举
            content: 切片内容（JSON 格式）

        Returns:
            创建的 ProfileSection 对象
        """
        section = ProfileSection(
            user_id=user_id,
            section_key=section_key,
            content=content
        )
        self.session.add(section)
        self.session.commit()
        self.session.refresh(section)
        return section

    def get_by_id(self, section_id: int) -> Optional[ProfileSection]:
        """
        根据 ID 获取画像切片

        Args:
            section_id: 切片 ID

        Returns:
            ProfileSection 对象，不存在则返回 None
        """
        return self.session.get(ProfileSection, section_id)

    def get_by_user_and_key(
        self,
        user_id: int,
        section_key: ProfileSectionKey
    ) -> Optional[ProfileSection]:
        """
        获取用户的指定类型切片

        Args:
            user_id: 用户 ID
            section_key: 切片类型枚举

        Returns:
            ProfileSection 对象，不存在则返回 None
        """
        statement = select(ProfileSection).where(
            ProfileSection.user_id == user_id,
            ProfileSection.section_key == section_key
        )
        return self.session.exec(statement).first()

    def get_all_by_user(self, user_id: int) -> List[ProfileSection]:
        """
        获取用户的所有画像切片

        Args:
            user_id: 用户 ID

        Returns:
            ProfileSection 对象列表
        """
        statement = select(ProfileSection).where(
            ProfileSection.user_id == user_id
        )
        return self.session.exec(statement).all()

    def get_user_profile_dict(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        """
        获取用户的完整画像，组装为字典格式
        用于 Agent 运行时加载

        Args:
            user_id: 用户 ID

        Returns:
            字典，键为 section_key 字符串，值为 content 字典
            例如: {"skills": {"programming": ["Python"]}, "education": {...}}
        """
        sections = self.get_all_by_user(user_id)
        profile_dict = {}
        for section in sections:
            profile_dict[section.section_key.value] = section.content
        return profile_dict

    def update(
        self,
        section_id: int,
        content: Dict[str, Any]
    ) -> Optional[ProfileSection]:
        """
        更新画像切片内容

        Args:
            section_id: 切片 ID
            content: 新的切片内容

        Returns:
            更新后的 ProfileSection 对象，不存在则返回 None
        """
        section = self.get_by_id(section_id)
        if section:
            section.content = content
            self.session.add(section)
            self.session.commit()
            self.session.refresh(section)
        return section

    def update_by_user_and_key(
        self,
        user_id: int,
        section_key: ProfileSectionKey,
        content: Dict[str, Any]
    ) -> Optional[ProfileSection]:
        """
        更新用户的指定类型切片内容（如果不存在则创建）

        Args:
            user_id: 用户 ID
            section_key: 切片类型枚举
            content: 新的切片内容

        Returns:
            更新或创建的 ProfileSection 对象
        """
        section = self.get_by_user_and_key(user_id, section_key)
        if section:
            # 更新现有切片
            section.content = content
            self.session.add(section)
            self.session.commit()
            self.session.refresh(section)
        else:
            # 创建新切片
            section = self.create(user_id, section_key, content)
        return section

    def delete(self, section_id: int) -> bool:
        """
        删除画像切片

        Args:
            section_id: 切片 ID

        Returns:
            删除成功返回 True，切片不存在返回 False
        """
        section = self.get_by_id(section_id)
        if section:
            self.session.delete(section)
            self.session.commit()
            return True
        return False

    def upsert_multiple(
        self,
        user_id: int,
        sections_data: Dict[ProfileSectionKey, Dict[str, Any]]
    ) -> List[ProfileSection]:
        """
        批量创建或更新画像切片

        Args:
            user_id: 用户 ID
            sections_data: 字典，键为 section_key，值为 content

        Returns:
            处理后的 ProfileSection 对象列表
        """
        result = []
        for section_key, content in sections_data.items():
            section = self.update_by_user_and_key(user_id, section_key, content)
            if section:
                result.append(section)
        return result
