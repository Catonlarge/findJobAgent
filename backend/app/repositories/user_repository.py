"""
用户管理 Repository
提供 users 表的增删改查操作
"""

from typing import Optional

from sqlmodel import Session, select

from app.models.user import User


class UserRepository:
    """
    用户数据访问对象
    封装所有与 users 表相关的数据库操作
    """

    def __init__(self, session: Session):
        """
        初始化 Repository

        Args:
            session: SQLModel 数据库会话
        """
        self.session = session

    def get_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            User 对象，不存在则返回 None
        """
        statement = select(User).where(User.username == username)
        return self.session.exec(statement).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        根据 ID 获取用户

        Args:
            user_id: 用户 ID

        Returns:
            User 对象，不存在则返回 None
        """
        return self.session.get(User, user_id)

    def get_or_create(self, username: str) -> User:
        """
        根据用户名获取用户，不存在则创建

        这是 ChatService 初始化的核心方法，实现"身份锚定"功能：
        将外部字符串 username 转换为内部整数 user_db_id

        Args:
            username: 用户名

        Returns:
            User 对象（已存在的或新创建的）
        """
        # 1. 尝试查询
        user = self.get_by_username(username)
        if user:
            return user

        # 2. 不存在，创建新用户
        print(f"[UserRepository] 检测到新用户 '{username}'，正在注册...")
        user = User(username=username, basic_info={"name": username})
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        print(f"[UserRepository] 新用户创建成功 (ID: {user.id})")
        return user

    def create(self, username: str, basic_info: Optional[dict] = None) -> User:
        """
        创建新用户

        Args:
            username: 用户名（必须唯一）
            basic_info: 基础信息字典（可选）

        Returns:
            创建的 User 对象
        """
        user = User(username=username, basic_info=basic_info or {})
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update_basic_info(self, user_id: int, basic_info: dict) -> Optional[User]:
        """
        更新用户基础信息

        Args:
            user_id: 用户 ID
            basic_info: 新的基础信息字典

        Returns:
            更新后的 User 对象，不存在则返回 None
        """
        user = self.get_by_id(user_id)
        if user:
            user.basic_info = basic_info
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
        return user
