"""
交付物版本管理 Repository
提供 artifacts 的增删改查操作，支持版本控制和血缘追踪
"""

from typing import List, Optional, Dict, Any

from sqlmodel import Session, select, col

from app.models.artifact import Artifact, ArtifactType, MatchRating
from app.models.job import JobDescription


class ArtifactRepository:
    """
    交付物版本管理数据访问对象
    封装所有与 artifacts 表相关的数据库操作
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
        group_id: int,
        version: int,
        artifact_type: ArtifactType,
        content: Dict[str, Any],
        session_id: Optional[int] = None,
        jd_id: Optional[int] = None,
        meta_summary: Optional[Dict[str, Any]] = None,
        schema_version: int = 1
    ) -> Artifact:
        """
        创建新交付物

        Args:
            user_id: 用户 ID
            group_id: 版本组 ID（同一份简历的所有版本共享此 ID）
            version: 版本号
            artifact_type: 交付物类型枚举
            content: 结构化内容（JSON 格式）
            session_id: 来源会话 ID（可选）
            jd_id: 关联 JD ID（可选）
            meta_summary: 列表摘要（可选）
            schema_version: JSON 结构版本号（默认为 1）

        Returns:
            创建的 Artifact 对象
        """
        artifact = Artifact(
            user_id=user_id,
            session_id=session_id,
            jd_id=jd_id,
            group_id=group_id,
            version=version,
            type=artifact_type,
            schema_version=schema_version,
            content=content,
            meta_summary=meta_summary or {}
        )
        self.session.add(artifact)
        self.session.commit()
        self.session.refresh(artifact)
        return artifact

    def get_by_id(self, artifact_id: int) -> Optional[Artifact]:
        """
        根据 ID 获取交付物

        Args:
            artifact_id: 交付物 ID

        Returns:
            Artifact 对象，不存在则返回 None
        """
        return self.session.get(Artifact, artifact_id)

    def get_by_group(self, group_id: int) -> List[Artifact]:
        """
        获取版本组的所有版本（按版本号倒序）

        Args:
            group_id: 版本组 ID

        Returns:
            Artifact 对象列表，按 version 倒序排列
        """
        statement = select(Artifact).where(
            Artifact.group_id == group_id
        ).order_by(col(Artifact.version).desc())
        return self.session.exec(statement).all()

    def get_latest_by_group(self, group_id: int) -> Optional[Artifact]:
        """
        获取版本组的最新版本

        Args:
            group_id: 版本组 ID

        Returns:
            最新版本的 Artifact 对象，不存在则返回 None
        """
        artifacts = self.get_by_group(group_id)
        return artifacts[0] if artifacts else None

    def get_all_by_user(
        self,
        user_id: int,
        artifact_type: Optional[ArtifactType] = None,
        limit: Optional[int] = None
    ) -> List[Artifact]:
        """
        获取用户的所有交付物（按创建时间倒序）

        Args:
            user_id: 用户 ID
            artifact_type: 过滤类型（可选）
            limit: 限制返回数量（可选）

        Returns:
            Artifact 对象列表，按 created_at 倒序排列
        """
        statement = select(Artifact).where(Artifact.user_id == user_id)

        if artifact_type:
            statement = statement.where(Artifact.type == artifact_type)

        statement = statement.order_by(col(Artifact.created_at).desc())

        if limit:
            statement = statement.limit(limit)

        return self.session.exec(statement).all()

    def get_by_session(self, session_id: int) -> List[Artifact]:
        """
        获取会话产生的所有交付物

        Args:
            session_id: 会话 ID

        Returns:
            Artifact 对象列表
        """
        statement = select(Artifact).where(
            Artifact.session_id == session_id
        ).order_by(col(Artifact.created_at).asc())
        return self.session.exec(statement).all()

    def get_by_jd(self, jd_id: int) -> List[Artifact]:
        """
        获取关联到某个 JD 的所有交付物

        Args:
            jd_id: JD ID

        Returns:
            Artifact 对象列表
        """
        statement = select(Artifact).where(
            Artifact.jd_id == jd_id
        ).order_by(col(Artifact.created_at).desc())
        return self.session.exec(statement).all()

    def create_new_version(
        self,
        user_id: int,
        artifact_type: ArtifactType,
        content: Dict[str, Any],
        session_id: Optional[int] = None,
        jd_id: Optional[int] = None,
        meta_summary: Optional[Dict[str, Any]] = None
    ) -> Artifact:
        """
        创建新版本的交付物（自动生成 group_id 和 version）

        Args:
            user_id: 用户 ID
            artifact_type: 交付物类型枚举
            content: 结构化内容（JSON 格式）
            session_id: 来源会话 ID（可选）
            jd_id: 关联 JD ID（可选）
            meta_summary: 列表摘要（可选）

        Returns:
            创建的 Artifact 对象
        """
        # 如果提供了 jd_id，尝试查找已有的版本组
        group_id = None
        version = 1

        if jd_id is not None:
            # 查找同一 JD 的最新版本
            statement = select(Artifact).where(
                Artifact.jd_id == jd_id,
                Artifact.type == artifact_type
            ).order_by(col(Artifact.version).desc()).limit(1)
            latest = self.session.exec(statement).first()

            if latest:
                group_id = latest.group_id
                version = latest.version + 1
            else:
                # 新建 group_id（使用 jd_id 作为 base，避免冲突）
                # 实际生产环境可能需要更复杂的 group_id 生成策略
                group_id = jd_id * 1000 + 1  # 简单策略：JD ID * 1000 + 类型偏移
        else:
            # 无 JD 关联的交付物，使用时间戳生成 group_id
            import time
            group_id = int(time.time())

        return self.create(
            user_id=user_id,
            group_id=group_id,
            version=version,
            artifact_type=artifact_type,
            content=content,
            session_id=session_id,
            jd_id=jd_id,
            meta_summary=meta_summary
        )

    def get_version_diff(
        self,
        artifact_id_1: int,
        artifact_id_2: int
    ) -> Optional[Dict[str, Any]]:
        """
        比较两个版本的差异（简单实现，仅比较 content）

        Args:
            artifact_id_1: 版本 1 的 ID
            artifact_id_2: 版本 2 的 ID

        Returns:
            差异字典，包含版本信息和内容差异
        """
        artifact_1 = self.get_by_id(artifact_id_1)
        artifact_2 = self.get_by_id(artifact_id_2)

        if not artifact_1 or not artifact_2:
            return None

        # 简单差异比较（实际生产环境可能需要更复杂的 diff 算法）
        return {
            "version_1": {
                "id": artifact_1.id,
                "version": artifact_1.version,
                "created_at": artifact_1.created_at.isoformat()
            },
            "version_2": {
                "id": artifact_2.id,
                "version": artifact_2.version,
                "created_at": artifact_2.created_at.isoformat()
            },
            "content_diff": {
                "version_1_content": artifact_1.content,
                "version_2_content": artifact_2.content
            }
        }

    def delete(self, artifact_id: int) -> bool:
        """
        删除交付物

        Args:
            artifact_id: 交付物 ID

        Returns:
            删除成功返回 True，交付物不存在返回 False
        """
        artifact = self.get_by_id(artifact_id)
        if artifact:
            self.session.delete(artifact)
            self.session.commit()
            return True
        return False

    def update_content(
        self,
        artifact_id: int,
        content: Dict[str, Any],
        meta_summary: Optional[Dict[str, Any]] = None
    ) -> Optional[Artifact]:
        """
        更新交付物内容（注意：这不会创建新版本，仅修改当前版本）

        Args:
            artifact_id: 交付物 ID
            content: 新的结构化内容
            meta_summary: 新的列表摘要（可选）

        Returns:
            更新后的 Artifact 对象，不存在则返回 None
        """
        artifact = self.get_by_id(artifact_id)
        if artifact:
            artifact.content = content
            if meta_summary is not None:
                artifact.meta_summary = meta_summary
            self.session.add(artifact)
            self.session.commit()
            self.session.refresh(artifact)
        return artifact
