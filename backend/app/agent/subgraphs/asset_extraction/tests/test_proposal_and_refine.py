"""
Proposal & Refine 子图单元测试

测试内容：
1. EditorLoader 节点：加载 L1 观察记录
2. Proposer 节点：批量生成草稿
3. Human 节点：人机交互断点
4. Refiner 节点：单条精修
5. SingleSaver 节点：即时存档
6. 路由函数：Scheduler 和 UserIntent Router
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes import (
    editor_loader_node,
    proposer_node,
    human_node,
    refiner_node,
    single_saver_node,
    route_scheduler,
    route_user_intent,
    _map_section_name_to_key,
    _format_observations_for_proposer,
)
from app.agent.subgraphs.asset_extraction.proposal_and_refine.state import (
    EditorState,
    ObservationSchema,
    ProfileItemSchema,
    ProposerOutput,
)
from app.models.observation import ObservationStatus


class TestMapSectionNameToKey:
    """测试 section_name 映射函数"""

    def test_map_skills(self):
        """测试映射技能分类"""
        from app.models.profile import ProfileSectionKey
        result = _map_section_name_to_key("技能")
        assert result == ProfileSectionKey.SKILLS

    def test_map_experience(self):
        """测试映射经历分类"""
        from app.models.profile import ProfileSectionKey
        result = _map_section_name_to_key("经历")
        assert result == ProfileSectionKey.WORK_EXPERIENCE

    def test_map_unknown(self):
        """测试映射未知分类（默认）"""
        from app.models.profile import ProfileSectionKey
        result = _map_section_name_to_key("未知")
        assert result == ProfileSectionKey.CAREER_POTENTIAL


class TestFormatObservationsForProposer:
    """测试观察记录格式化函数"""

    def test_format_empty_observations(self):
        """测试空观察列表"""
        result = _format_observations_for_proposer([])
        assert result == "【暂无观察记录】"

    def test_format_observations(self):
        """测试格式化观察列表"""
        observations = [
            ObservationSchema(
                id=1,
                fact_content="掌握 Python",
                category="skills",
                confidence=0.9,
                is_potential_signal=False
            ),
            ObservationSchema(
                id=2,
                fact_content="有领导力潜能",
                category="traits",
                confidence=0.85,
                is_potential_signal=True
            )
        ]
        result = _format_observations_for_proposer(observations)

        assert "[ID:1]" in result
        assert "skills" in result
        assert "掌握 Python" in result
        assert "[ID:2]" in result
        assert "traits" in result
        assert "[潜力信号]" in result


class TestEditorLoaderNode:
    """测试 EditorLoader 节点"""

    @patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine")
    @patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.Session")
    def test_editor_loader_loads_pending_observations(
        self,
        mock_session_class,
        mock_get_engine,
        mock_runnable_config,
        mock_editor_state
    ):
        """测试加载 pending 状态的观察记录"""
        # 设置 Mock
        mock_engine = Mock()
        mock_get_engine.return_value = mock_engine

        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        # 模拟数据库查询结果
        mock_obs = Mock()
        mock_obs.id = 1
        mock_obs.fact_content = "掌握 Python"
        mock_obs.category = Mock(value="skills")
        mock_obs.source_msg_uuid = "msg_123"
        mock_obs.confidence = 0.9
        mock_obs.is_potential_signal = False
        mock_obs.created_at = Mock()

        mock_session.exec.return_value.all.return_value = [mock_obs]

        # 执行
        result = editor_loader_node(mock_editor_state, mock_runnable_config)

        # 验证
        assert "raw_materials" in result
        assert len(result["raw_materials"]) == 1
        assert result["raw_materials"][0].fact_content == "掌握 Python"
        assert result["active_index"] == 0
        assert result["current_drafts"] == []


class TestProposerNode:
    """测试 Proposer 节点"""

    @patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_llm")
    def test_proposer_no_raw_materials(self, mock_get_llm, mock_editor_state, mock_runnable_config):
        """测试没有原材料时的处理"""
        mock_editor_state["raw_materials"] = []

        # 执行
        result = proposer_node(mock_editor_state, mock_runnable_config)

        # 验证
        assert result["current_drafts"] == []
        assert result["active_index"] == 0
        assert len(result["messages"]) == 1
        assert "暂无可整理" in result["messages"][0].content

    @patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_llm")
    def test_proposer_generates_drafts(
        self,
        mock_get_llm,
        mock_runnable_config,
        sample_observations
    ):
        """测试生成草稿"""
        # 设置 Mock
        mock_llm = Mock()

        mock_proposer_output = ProposerOutput(
            drafts=[
                ProfileItemSchema(
                    standard_content="掌握 Python 编程语言",
                    tags=["Python", "编程"],
                    source_l1_ids=[1, 2],
                    section_name="技能"
                ),
                ProfileItemSchema(
                    standard_content="有 3 年后端开发经验",
                    tags=["后端", "经验"],
                    source_l1_ids=[3],
                    section_name="经历"
                )
            ],
            analysis_summary="从 3 条观察中提炼出 2 条草稿"
        )

        mock_structured = Mock()
        mock_structured.invoke.return_value = mock_proposer_output
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        # 设置状态 - 添加 id 字段到每个观察
        raw_materials = [
            ObservationSchema(id=i+1, **obs) for i, obs in enumerate(sample_observations)
        ]
        state = {
            "raw_materials": raw_materials,
            "current_drafts": [],
            "active_index": 0,
            "messages": []
        }

        # 执行
        result = proposer_node(state, mock_runnable_config)

        # 验证
        assert len(result["current_drafts"]) == 2
        assert result["active_index"] == 0
        assert result["current_drafts"][0].section_name == "技能"


class TestHumanNode:
    """测试 Human 节点"""

    def test_human_node_valid_index(self, sample_observations):
        """测试有效索引时的展示"""
        drafts = [
            ProfileItemSchema(
                standard_content="掌握 Python",
                tags=["Python"],
                source_l1_ids=[1],
                section_name="技能"
            )
        ]
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": drafts,
            "active_index": 0,
            "messages": []
        }

        # 执行
        result = human_node(state, Mock())

        # 验证：状态不变，只是中间节点
        assert result == state

    def test_human_node_invalid_index(self):
        """测试无效索引时"""
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [],
            "active_index": 5,
            "messages": []
        }

        # 执行
        result = human_node(state, Mock())

        # 验证
        assert result == state


class TestRouteScheduler:
    """测试 Scheduler 路由"""

    def test_scheduler_continue_processing(self):
        """测试继续处理（有草稿待处理）"""
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [Mock(), Mock(), Mock()],
            "active_index": 1,
            "messages": []
        }

        result = route_scheduler(state)
        assert result == "human_node"

    def test_scheduler_end_processing(self):
        """测试结束处理（所有草稿已处理）"""
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [Mock(), Mock()],
            "active_index": 2,
            "messages": []
        }

        result = route_scheduler(state)
        assert result == "__end__"


class TestRouteUserIntent:
    """测试用户意图路由"""

    def test_route_confirm_keywords(self):
        """测试确认关键词路由到 SingleSaver"""
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [],
            "active_index": 0,
            "messages": [HumanMessage(content="确认")]
        }

        result = route_user_intent(state)
        assert result == "single_saver_node"

    def test_route_confirm_with_ok(self):
        """测试 'ok' 路由到 SingleSaver"""
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [],
            "active_index": 0,
            "messages": [HumanMessage(content="OK, 保存吧")]
        }

        result = route_user_intent(state)
        assert result == "single_saver_node"

    def test_route_modify_to_refiner(self):
        """测试修改意图路由到 Refiner"""
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [],
            "active_index": 0,
            "messages": [HumanMessage(content="请把这段改得更专业一点")]
        }

        result = route_user_intent(state)
        assert result == "refiner_node"

    def test_route_no_messages_defaults_to_refiner(self):
        """测试没有消息时默认路由到 Refiner"""
        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [],
            "active_index": 0,
            "messages": []
        }

        result = route_user_intent(state)
        assert result == "refiner_node"


class TestRefinerNode:
    """测试 Refiner 节点"""

    @patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_llm")
    def test_refiner_modifies_draft(self, mock_get_llm, mock_runnable_config):
        """测试修改草稿"""
        # 设置 Mock
        mock_llm = Mock()

        refined_draft = ProfileItemSchema(
            standard_content="精通 Python 编程语言及生态",
            tags=["Python", "后端开发"],
            source_l1_ids=[1],
            section_name="技能"
        )

        mock_structured = Mock()
        mock_structured.invoke.return_value = refined_draft
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        # 设置状态
        drafts = [
            ProfileItemSchema(
                standard_content="掌握 Python",
                tags=["Python"],
                source_l1_ids=[1],
                section_name="技能"
            )
        ]

        state: EditorState = {
            "raw_materials": [],
            "current_drafts": drafts,
            "active_index": 0,
            "messages": [HumanMessage(content="请改得更专业一些")]
        }

        # 执行
        result = refiner_node(state, mock_runnable_config)

        # 验证
        assert "current_drafts" in result
        assert result["current_drafts"][0].standard_content == "精通 Python 编程语言及生态"
        # active_index 不变
        assert "active_index" not in result


class TestSingleSaverNode:
    """测试 SingleSaver 节点"""

    @patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.Session")
    @patch("app.agent.subgraphs.asset_extraction.proposal_and_refine.nodes.get_engine")
    def test_single_saver_saves_draft(
        self,
        mock_get_engine,
        mock_session_class,
        mock_runnable_config
    ):
        """测试保存草稿"""
        # 设置 Mock
        mock_engine = Mock()
        mock_get_engine.return_value = mock_engine

        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        # 设置状态
        draft = ProfileItemSchema(
            standard_content="掌握 Python",
            tags=["Python"],
            source_l1_ids=[1, 2],
            section_name="技能"
        )

        state: EditorState = {
            "raw_materials": [],
            "current_drafts": [draft],
            "active_index": 0,
            "messages": []
        }

        # 执行
        result = single_saver_node(state, mock_runnable_config)

        # 验证
        assert result["active_index"] == 1  # 游标前进
        assert result["messages"] == []  # 清空消息
        mock_session.add.assert_called()  # 验证添加了记录
