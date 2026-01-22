"""
Proposal & Refine 子图节点单元测试
验证 editor_loader_node 和 single_saver_node 的 username 解析功能
"""

import pytest
from unittest.mock import patch, Mock
from langgraph.graph.state import RunnableConfig

from app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes import (
    editor_loader_node,
    single_saver_node,
    _get_username_from_config,
)
from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import (
    EditorState,
    ObservationSchema,
    ProfileItemSchema,
)
from app.models.observation import RawObservation, ObservationCategory, ObservationStatus
from app.models.user import User
from sqlmodel import select


class TestGetUsernameFromConfig:
    """测试 _get_username_from_config 辅助函数"""

    def test_get_username_from_config_with_username(self):
        """测试从 config 中正确获取 username"""
        config = RunnableConfig(configurable={"username": "test_user"})
        result = _get_username_from_config(config)
        assert result == "test_user"

    def test_get_username_from_config_default(self):
        """测试默认返回 'me'"""
        config = RunnableConfig(configurable={})
        result = _get_username_from_config(config)
        assert result == "me"

    def test_get_username_from_config_empty_configurable(self):
        """测试 configurable 为空时默认返回 'me'"""
        config = RunnableConfig({})
        result = _get_username_from_config(config)
        assert result == "me"

    def test_get_username_from_config_invalid_type(self):
        """测试 username 类型错误时抛出异常"""
        config = RunnableConfig(configurable={"username": 123})
        with pytest.raises(ValueError, match="username must be a string"):
            _get_username_from_config(config)


class TestEditorLoaderNode:
    """测试 editor_loader_node 的 username 解析功能"""

    def _mock_get_or_create_user(self, user, test_db_session):
        """Mock get_or_create_user to return test database user"""
        def side_effect(username):
            # 查找测试数据库中的用户
            statement = select(User).where(User.username == username)
            found_user = test_db_session.exec(statement).first()
            if found_user:
                return found_user
            # 如果不存在，创建新用户
            new_user = User(username=username)
            test_db_session.add(new_user)
            test_db_session.commit()
            test_db_session.refresh(new_user)
            return new_user
        return side_effect

    def test_editor_loader_loads_observations_for_correct_user(
        self, test_db_session, test_user
    ):
        """测试 editor_loader 只加载指定用户的 pending 观察"""
        # 创建测试用户的不同 pending 观察
        obs1 = RawObservation(
            user_id=test_user.id,
            category=ObservationCategory.SKILL,
            fact_content="擅长 Python 编程",
            confidence=90,
            is_potential_signal=False,
            status=ObservationStatus.PENDING,
        )
        obs2 = RawObservation(
            user_id=test_user.id,
            category=ObservationCategory.TRAIT,
            fact_content="做事很有耐心",
            confidence=85,
            is_potential_signal=False,
            status=ObservationStatus.PENDING,
        )
        test_db_session.add(obs1)
        test_db_session.add(obs2)
        test_db_session.commit()

        # 创建另一个用户及其观察（应该不被加载）
        other_user = User(username="other_user")
        test_db_session.add(other_user)
        test_db_session.commit()
        test_db_session.refresh(other_user)

        obs3 = RawObservation(
            user_id=other_user.id,
            category=ObservationCategory.SKILL,
            fact_content="擅长 Java 编程",
            confidence=80,
            is_potential_signal=False,
            status=ObservationStatus.PENDING,
        )
        test_db_session.add(obs3)
        test_db_session.commit()

        # 使用 test_user.username 作为 config
        config = RunnableConfig(configurable={"username": test_user.username})
        state = EditorState()

        # Mock get_engine 返回测试数据库
        with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine") as mock_engine:
            mock_engine.return_value = test_db_session.get_bind()

            # Mock get_or_create_user 使用测试数据库
            with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_or_create_user") as mock_get_user:
                mock_get_user.side_effect = self._mock_get_or_create_user(None, test_db_session)

                result = editor_loader_node(state, config)

        # 验证只加载了 test_user 的观察
        raw_materials = result["raw_materials"]
        assert len(raw_materials) == 2
        fact_contents = [m.fact_content for m in raw_materials]
        assert "擅长 Python 编程" in fact_contents
        assert "做事很有耐心" in fact_contents
        assert "擅长 Java 编程" not in fact_contents

    def test_editor_loader_only_loads_pending_status(
        self, test_db_session, test_user
    ):
        """测试 editor_loader 只加载 PENDING 状态的观察"""
        # 创建 pending 状态的观察
        obs_pending = RawObservation(
            user_id=test_user.id,
            category=ObservationCategory.SKILL,
            fact_content="待处理的观察",
            confidence=90,
            is_potential_signal=False,
            status=ObservationStatus.PENDING,
        )
        # 创建 promoted 状态的观察（应该不被加载）
        obs_promoted = RawObservation(
            user_id=test_user.id,
            category=ObservationCategory.TRAIT,
            fact_content="已处理的观察",
            confidence=85,
            is_potential_signal=False,
            status=ObservationStatus.PROMOTED,
        )
        test_db_session.add(obs_pending)
        test_db_session.add(obs_promoted)
        test_db_session.commit()

        config = RunnableConfig(configurable={"username": test_user.username})
        state = EditorState()

        with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine") as mock_engine:
            mock_engine.return_value = test_db_session.get_bind()

            with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_or_create_user") as mock_get_user:
                mock_get_user.side_effect = self._mock_get_or_create_user(None, test_db_session)

                result = editor_loader_node(state, config)

        # 只加载 pending 状态的观察
        raw_materials = result["raw_materials"]
        assert len(raw_materials) == 1
        assert raw_materials[0].fact_content == "待处理的观察"

    def test_editor_loader_resolves_username_to_user_id(
        self, test_db_session
    ):
        """测试 editor_loader 正确将 username 解析为 user_id"""
        # 创建用户和观察
        user = User(username="resolver_test_user")
        test_db_session.add(user)
        test_db_session.commit()
        test_db_session.refresh(user)

        obs = RawObservation(
            user_id=user.id,
            category=ObservationCategory.SKILL,
            fact_content="测试 username 解析",
            confidence=90,
            is_potential_signal=False,
            status=ObservationStatus.PENDING,
        )
        test_db_session.add(obs)
        test_db_session.commit()

        # 使用 username 而不是 user_id
        config = RunnableConfig(configurable={"username": user.username})
        state = EditorState()

        with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine") as mock_engine:
            mock_engine.return_value = test_db_session.get_bind()

            with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_or_create_user") as mock_get_user:
                mock_get_user.side_effect = self._mock_get_or_create_user(None, test_db_session)

                result = editor_loader_node(state, config)

        # 验证正确加载了观察
        raw_materials = result["raw_materials"]
        assert len(raw_materials) == 1
        assert raw_materials[0].fact_content == "测试 username 解析"

    def test_editor_loader_returns_empty_list_when_no_observations(
        self, test_db_session, test_user
    ):
        """测试没有观察时返回空列表"""
        config = RunnableConfig(configurable={"username": test_user.username})
        state = EditorState()

        with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine") as mock_engine:
            mock_engine.return_value = test_db_session.get_bind()

            with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_or_create_user") as mock_get_user:
                mock_get_user.side_effect = self._mock_get_or_create_user(None, test_db_session)

                result = editor_loader_node(state, config)

        assert result["raw_materials"] == []
        assert result["current_drafts"] == []
        assert result["active_index"] == 0
        assert result["messages"] == []


class TestSingleSaverNode:
    """测试 single_saver_node 的 username 解析功能"""

    def _mock_get_or_create_user(self, user, test_db_session):
        """Mock get_or_create_user to return test database user"""
        def side_effect(username):
            # 查找测试数据库中的用户
            statement = select(User).where(User.username == username)
            found_user = test_db_session.exec(statement).first()
            if found_user:
                return found_user
            # 如果不存在，创建新用户
            new_user = User(username=username)
            test_db_session.add(new_user)
            test_db_session.commit()
            test_db_session.refresh(new_user)
            return new_user
        return side_effect

    def test_single_saver_saves_to_correct_user(
        self, test_db_session, test_user
    ):
        """测试 single_saver 保存到正确的用户"""
        # 创建测试草稿
        draft = ProfileItemSchema(
            standard_content="我掌握 Python 和 FastAPI",
            tags=["Python", "FastAPI", "后端开发"],
            source_l1_ids=[],
            section_name="技能"
        )

        state = EditorState(
            current_drafts=[draft],
            active_index=0,
            messages=[]
        )

        # 使用 test_user.username 作为 config
        config = RunnableConfig(configurable={"username": test_user.username})

        with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine") as mock_engine:
            mock_engine.return_value = test_db_session.get_bind()

            with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_or_create_user") as mock_get_user:
                mock_get_user.side_effect = self._mock_get_or_create_user(None, test_db_session)

                result = single_saver_node(state, config)

        # 验证保存到正确的用户
        from app.models.profile import ProfileSection

        saved_sections = test_db_session.exec(
            select(ProfileSection).where(ProfileSection.user_id == test_user.id)
        ).all()

        assert len(saved_sections) == 1
        assert saved_sections[0].content["standard_content"] == "我掌握 Python 和 FastAPI"

        # 验证翻页逻辑
        assert result["active_index"] == 1
        assert result["messages"] == []

    def test_single_saver_promotes_l1_observations(
        self, test_db_session, test_user
    ):
        """测试 single_saver 正确核销 L1 观察"""
        # 创建 pending 状态的 L1 观察
        l1_obs = RawObservation(
            user_id=test_user.id,
            category=ObservationCategory.SKILL,
            fact_content="擅长 Python 编程",
            confidence=90,
            is_potential_signal=False,
            status=ObservationStatus.PENDING,
        )
        test_db_session.add(l1_obs)
        test_db_session.commit()
        test_db_session.refresh(l1_obs)

        # 创建关联的草稿
        draft = ProfileItemSchema(
            standard_content="我掌握 Python 编程",
            tags=["Python"],
            source_l1_ids=[l1_obs.id],
            section_name="技能"
        )

        state = EditorState(
            current_drafts=[draft],
            active_index=0,
            messages=[]
        )

        config = RunnableConfig(configurable={"username": test_user.username})

        with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine") as mock_engine:
            mock_engine.return_value = test_db_session.get_bind()

            with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_or_create_user") as mock_get_user:
                mock_get_user.side_effect = self._mock_get_or_create_user(None, test_db_session)

                single_saver_node(state, config)

        # 验证 L1 观察状态翻转为 PROMOTED
        test_db_session.refresh(l1_obs)
        assert l1_obs.status == ObservationStatus.PROMOTED

    def test_single_saver_resolves_username_to_user_id(
        self, test_db_session
    ):
        """测试 single_saver 正确将 username 解析为 user_id"""
        # 创建用户
        user = User(username="saver_test_user")
        test_db_session.add(user)
        test_db_session.commit()
        test_db_session.refresh(user)

        draft = ProfileItemSchema(
            standard_content="测试 username 解析",
            tags=["测试"],
            source_l1_ids=[],
            section_name="技能"
        )

        state = EditorState(
            current_drafts=[draft],
            active_index=0,
            messages=[]
        )

        # 使用 username 而不是 user_id
        config = RunnableConfig(configurable={"username": user.username})

        with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine") as mock_engine:
            mock_engine.return_value = test_db_session.get_bind()

            with patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_or_create_user") as mock_get_user:
                mock_get_user.side_effect = self._mock_get_or_create_user(None, test_db_session)

                result = single_saver_node(state, config)

        # 验证保存到正确的用户
        from app.models.profile import ProfileSection

        saved_sections = test_db_session.exec(
            select(ProfileSection).where(ProfileSection.user_id == user.id)
        ).all()

        assert len(saved_sections) == 1
        assert saved_sections[0].content["standard_content"] == "测试 username 解析"

    def test_single_saver_handles_index_out_of_range(
        self, test_db_session, test_user
    ):
        """测试索引超出范围时不处理"""
        state = EditorState(
            current_drafts=[],
            active_index=0,
            messages=[]
        )

        config = RunnableConfig(configurable={"username": test_user.username})

        result = single_saver_node(state, config)

        # 索引超出范围时，应该直接返回 state
        assert result == state
