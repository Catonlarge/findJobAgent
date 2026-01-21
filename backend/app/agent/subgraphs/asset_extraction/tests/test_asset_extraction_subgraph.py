"""
Asset Extraction 父图单元测试

测试内容：
1. 联合状态（AssetExtractionState）
2. 父图路由（asset_extraction_router）
3. 子图创建函数
4. 父图编译
"""

import pytest
from unittest.mock import Mock, patch
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.subgraphs.asset_extraction.asset_extraction_subgraph import (
    AssetExtractionState,
    asset_extraction_router,
    create_asset_extraction_subgraph,
)


class TestAssetExtractionState:
    """测试联合状态定义"""

    def test_state_contains_chat_fields(self):
        """测试状态包含 chat_and_profile 字段"""
        state: AssetExtractionState = {
            "messages": [],
            "l1_observations_summary": "",
            "last_turn_analysis": None,
            "session_new_observation_count": 0,
            "last_user_message": None
        }
        assert "messages" in state
        assert "l1_observations_summary" in state
        assert "last_turn_analysis" in state

    def test_state_contains_proposal_fields(self):
        """测试状态包含 proposal_and_refine 字段"""
        state: AssetExtractionState = {
            "pending_proposals": [],
            "user_feedback": {},
            "current_stage": "chat",
            "saved_assets": []
        }
        assert "pending_proposals" in state
        assert "user_feedback" in state
        assert "current_stage" in state
        assert "saved_assets" in state

    def test_state_combined_fields(self):
        """测试状态可以同时包含两个子图的字段"""
        state: AssetExtractionState = {
            # Chat & Profile 字段
            "messages": [HumanMessage(content="你好")],
            "l1_observations_summary": "技能: Python",
            "last_turn_analysis": {"has_new_info": True},
            "session_new_observation_count": 5,
            "last_user_message": HumanMessage(content="你好"),
            # Proposal & Refine 字段
            "pending_proposals": [],
            "user_feedback": {},
            "current_stage": "proposal",
            "saved_assets": []
        }
        assert len(state["messages"]) == 1
        assert state["session_new_observation_count"] == 5
        assert state["current_stage"] == "proposal"


class TestAssetExtractionRouter:
    """测试父图路由函数"""

    def test_router_no_analysis_continues_chat(self):
        """测试没有分析结果时继续聊天"""
        state: AssetExtractionState = {"last_turn_analysis": None}
        result = asset_extraction_router(state)
        assert result == "continue_chat"

    def test_router_below_threshold_continues_chat(self):
        """测试未达到阈值时继续聊天"""
        state: AssetExtractionState = {
            "last_turn_analysis": {
                "has_new_info": True,
                "new_observation_count": 3,
                "is_ready_to_refine": False
            }
        }
        result = asset_extraction_router(state)
        assert result == "continue_chat"

    def test_router_above_threshold_enters_refinement(self):
        """测试达到阈值时进入整理阶段"""
        state: AssetExtractionState = {
            "last_turn_analysis": {
                "has_new_info": True,
                "new_observation_count": 2,
                "is_ready_to_refine": True
            }
        }
        result = asset_extraction_router(state)
        assert result == "enter_refinement"

    def test_router_missing_is_ready_key_continues_chat(self):
        """测试缺少 is_ready_to_refine 键时默认继续聊天"""
        state: AssetExtractionState = {
            "last_turn_analysis": {
                "has_new_info": True
            }
        }
        result = asset_extraction_router(state)
        assert result == "continue_chat"


class TestCreateAssetExtractionSubgraph:
    """测试父图创建函数"""

    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_chat_and_profile_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_proposal_and_refine_subgraph")
    def test_create_subgraph_without_checkpointer(
        self,
        mock_create_proposal,
        mock_create_chat
    ):
        """测试不带 checkpointer 创建父图"""
        # 设置 Mock
        mock_chat_subgraph = Mock()
        mock_proposal_subgraph = Mock()
        mock_create_chat.return_value = mock_chat_subgraph
        mock_create_proposal.return_value = mock_proposal_subgraph

        # 执行
        graph = create_asset_extraction_subgraph(checkpointer=None)

        # 验证
        assert graph is not None
        mock_create_chat.assert_called_once()
        mock_create_proposal.assert_called_once()

    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_chat_and_profile_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_proposal_and_refine_subgraph")
    def test_create_subgraph_with_checkpointer(
        self,
        mock_create_proposal,
        mock_create_chat
    ):
        """测试带 checkpointer 创建父图"""
        # 设置 Mock
        mock_chat_subgraph = Mock()
        mock_proposal_subgraph = Mock()
        mock_create_chat.return_value = mock_chat_subgraph
        mock_create_proposal.return_value = mock_proposal_subgraph

        mock_checkpointer = Mock()

        # 执行
        graph = create_asset_extraction_subgraph(checkpointer=mock_checkpointer)

        # 验证
        assert graph is not None

    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_chat_and_profile_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_proposal_and_refine_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.StateGraph")
    def test_graph_structure(
        self,
        mock_stategraph_class,
        mock_create_proposal,
        mock_create_chat
    ):
        """测试图结构是否正确"""
        # 设置 Mock
        mock_chat_subgraph = Mock()
        mock_proposal_subgraph = Mock()
        mock_create_chat.return_value = mock_chat_subgraph
        mock_create_proposal.return_value = mock_proposal_subgraph

        mock_workflow = Mock()
        mock_stategraph_class.return_value = mock_workflow

        mock_compiled = Mock()
        mock_workflow.compile.return_value = mock_compiled

        # 执行
        result = create_asset_extraction_subgraph()

        # 验证图结构
        mock_workflow.set_entry_point.assert_called_once_with("chat_and_profile")
        mock_workflow.add_node.assert_any_call("chat_and_profile", mock_chat_subgraph)
        mock_workflow.add_node.assert_any_call("proposal_and_refine", mock_proposal_subgraph)


class TestSubgraphIntegration:
    """测试子图集成"""

    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_chat_and_profile_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_proposal_and_refine_subgraph")
    def test_state_flows_between_subgraphs(
        self,
        mock_create_proposal,
        mock_create_chat
    ):
        """测试状态在子图间流转"""
        # 设置 Mock
        mock_chat_subgraph = Mock()
        mock_proposal_subgraph = Mock()
        mock_create_chat.return_value = mock_chat_subgraph
        mock_create_proposal.return_value = mock_proposal_subgraph

        # 创建父图
        graph = create_asset_extraction_subgraph()

        # 验证
        assert graph is not None
        # 实际的状态流转测试需要 LangGraph 的 invoke，这里只验证创建成功


class TestEntryPointsAndEdges:
    """测试入口点和边"""

    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_chat_and_profile_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_proposal_and_refine_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.StateGraph")
    def test_default_entry_point(
        self,
        mock_stategraph_class,
        mock_create_proposal,
        mock_create_chat
    ):
        """测试默认入口点是 chat_and_profile"""
        # 设置 Mock
        mock_chat_subgraph = Mock()
        mock_proposal_subgraph = Mock()
        mock_create_chat.return_value = mock_chat_subgraph
        mock_create_proposal.return_value = mock_proposal_subgraph

        mock_workflow = Mock()
        mock_stategraph_class.return_value = mock_workflow

        mock_compiled = Mock()
        mock_workflow.compile.return_value = mock_compiled

        # 执行
        create_asset_extraction_subgraph()

        # 验证入口点
        mock_workflow.set_entry_point.assert_called_once_with("chat_and_profile")

    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_chat_and_profile_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.create_proposal_and_refine_subgraph")
    @patch("app.agent.subgraphs.asset_extraction.asset_extraction_subgraph.StateGraph")
    def test_proposal_to_end_edge(
        self,
        mock_stategraph_class,
        mock_create_proposal,
        mock_create_chat
    ):
        """测试 proposal_and_refine 到 END 的边"""
        # 设置 Mock
        mock_chat_subgraph = Mock()
        mock_proposal_subgraph = Mock()
        mock_create_chat.return_value = mock_chat_subgraph
        mock_create_proposal.return_value = mock_proposal_subgraph

        mock_workflow = Mock()
        mock_stategraph_class.return_value = mock_workflow

        from langgraph.graph import END
        mock_compiled = Mock()
        mock_workflow.compile.return_value = mock_compiled

        # 执行
        create_asset_extraction_subgraph()

        # 验证有 proposal_and_refine -> END 的边
        # 注意：由于 add_edge 可能被多次调用，这里只验证至少有一次
        assert mock_workflow.add_edge.called
        edge_calls = mock_workflow.add_edge.call_args_list
        # 检查是否有 proposal_and_refine 到 END 的调用
        has_proposal_end_edge = any(
            call[0][0] == "proposal_and_refine" and call[0][1] == END
            for call in edge_calls
        )
        assert has_proposal_end_edge, "Should have edge from proposal_and_refine to END"
