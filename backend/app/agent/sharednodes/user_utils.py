"""
用户相关的通用工具函数

提供跨节点复用的用户操作工具函数。
"""

from sqlmodel import Session, select
from app.db.init_db import get_engine
from app.models.user import User


def get_or_create_user(username: str) -> User:
    """
    获取或创建用户（Get-or-Create 模式）

    这是一个通用的工具函数，用于在任何需要用户 ID 的节点中
    安全地获取用户对象。如果用户不存在，会自动创建新用户。

    Args:
        username: 用户名

    Returns:
        User: 用户对象（已持久化到数据库）

    Raises:
        Exception: 数据库操作失败时抛出异常
    """
    engine = get_engine()
    with Session(engine) as session:
        # 查询用户
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()

        # 如果用户不存在，创建新用户
        if not user:
            user = User(username=username, basic_info={})
            session.add(user)
            session.commit()
            session.refresh(user)

        return user


def get_user_id(username: str) -> int:
    """
    获取用户 ID（如果用户不存在则自动创建）

    这是一个简化的版本，直接返回用户 ID。
    使用场景：只需要 user_id 而不需要完整 User 对象时。

    Args:
        username: 用户名

    Returns:
        int: 用户 ID

    Raises:
        Exception: 数据库操作失败时抛出异常
    """
    user = get_or_create_user(username)
    return user.id


def user_exists(username: str) -> bool:
    """
    检查用户是否存在（不创建用户）

    Args:
        username: 用户名

    Returns:
        bool: 用户是否存在
    """
    engine = get_engine()
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()
        return user is not None
