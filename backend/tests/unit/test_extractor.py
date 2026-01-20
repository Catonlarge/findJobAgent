"""
隐性资产提取器单元测试 (T2-01.2)

测试提取器从用户消息中提取有价值职业信息的功能。
包括 LLM 提取、路由决策、数据库操作等测试。
"""

import sys
import os
import pytest
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.agent.nodes.extractor import extractor_node
from app.agent.nodes.db_ops import save_asset_node, discard_asset_node
from app.agent.nodes.router import router_decision_function
from app.agent.models import AssetProposal, EmptyProposal
from app.models.profile import ProfileSectionKey
from app.models.chat import ChatIntent


class TestExtractorNode:
    """测试提取器节点"""

    def test_no_messages_returns_no_proposal(self):
        """测试：无消息时无提案"""
        state = {"messages": []}
        result = extractor_node(state)
        assert result["pending_proposal"] is None

    def test_non_user_message_returns_no_proposal(self):
        """测试：非用户消息无提案"""
        state = {
            "messages": [
                {"role": "assistant", "content": "Hello"}
            ]
        }
        result = extractor_node(state)
        assert result["pending_proposal"] is None

    @patch('app.agent.nodes.extractor.get_llm')
    def test_skill_extraction_generates_proposal(self, mock_get_llm):
        """测试：提取技能生成提案"""
        # Mock LLM 返回结构化输出
        mock_llm = Mock()
        mock_structured = Mock()
        mock_structured.invoke.return_value = AssetProposal(
            section_key=ProfileSectionKey.SKILLS,
            refined_content="我掌握 Python 和 FastAPI",
            thought="用户明确提到技术栈"
        )
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        state = {
            "messages": [
                {"role": "user", "content": "我精通 Python 和 FastAPI"}
            ],
            "user_id": 1
        }

        result = extractor_node(state)

        # 验证提案生成
        assert result["pending_proposal"] is not None
        assert result["pending_proposal"]["section_key"] == "skills"
        assert "Python" in result["pending_proposal"]["refined_content"]

        # 验证确认消息
        assert len(result["messages"]) == 2
        assert "存入档案" in result["messages"][1]["content"]

    @patch('app.agent.nodes.extractor.get_llm')
    def test_career_potential_extraction(self, mock_get_llm):
        """测试：提取职业潜能生成提案 (T2-01.2 新增枚举值)"""
        mock_llm = Mock()
        mock_structured = Mock()
        mock_structured.invoke.return_value = AssetProposal(
            section_key=ProfileSectionKey.CAREER_POTENTIAL,
            refined_content="我对 AI 框架很有兴趣，打算深入研究",
            thought="用户表达了技术热情和探索方向"
        )
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        state = {
            "messages": [
                {"role": "user", "content": "我觉得那个 AI 框架很有意思，想试试"}
            ],
            "user_id": 1
        }

        result = extractor_node(state)

        # 验证提案生成
        assert result["pending_proposal"] is not None
        assert result["pending_proposal"]["section_key"] == "career_potential"
        assert "AI 框架" in result["pending_proposal"]["refined_content"]

    @patch('app.agent.nodes.extractor.get_llm')
    def test_refinement_mode_with_pending_proposal(self, mock_get_llm):
        """测试：调整模式 - 当 pending_proposal 存在时，使用调整 prompt"""
        mock_llm = Mock()
        mock_structured = Mock()
        mock_structured.invoke.return_value = AssetProposal(
            section_key=ProfileSectionKey.SKILLS,
            refined_content="掌握 Python",
            thought="根据用户反馈简化了表述"
        )
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        state = {
            "messages": [
                {"role": "user", "content": "太啰嗦了"}
            ],
            "user_id": 1,
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "我精通 Python 编程语言，并且有丰富的开发经验",
                "thought": "用户提到技术栈"
            }
        }

        result = extractor_node(state)

        # 验证提案调整
        assert result["pending_proposal"] is not None
        assert result["pending_proposal"]["refined_content"] == "掌握 Python"

        # 验证使用了调整模板
        assert len(result["messages"]) == 2
        assert "已调整提案" in result["messages"][1]["content"]

        # 验证 LLM 被正确调用（应该使用调整 prompt）
        mock_structured.invoke.assert_called_once()
        call_args = mock_structured.invoke.call_args
        prompt = call_args[0][0]
        assert "之前的提案" in prompt
        assert "用户的反馈" in prompt

    @patch('app.agent.nodes.extractor.get_llm')
    def test_refinement_mode_user_abandon(self, mock_get_llm):
        """测试：调整模式 - 用户要求放弃提案"""
        mock_llm = Mock()
        mock_structured = Mock()
        mock_structured.invoke.return_value = EmptyProposal(is_empty=True)
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        state = {
            "messages": [
                {"role": "user", "content": "不要了，算了"}
            ],
            "user_id": 1,
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "我精通 Python",
                "thought": "用户提到技术栈"
            }
        }

        result = extractor_node(state)

        # 验证提案被清空
        assert result["pending_proposal"] is None

    @patch('app.agent.nodes.extractor.get_llm')
    def test_empty_proposal_when_no_asset_detected(self, mock_get_llm):
        """测试：无资产时返回空提案"""
        mock_llm = Mock()
        mock_structured = Mock()
        mock_structured.invoke.return_value = EmptyProposal(is_empty=True)
        mock_llm.with_structured_output.return_value = mock_structured
        mock_get_llm.return_value = mock_llm

        state = {
            "messages": [
                {"role": "user", "content": "今天天气不错"}
            ],
            "user_id": 1
        }

        result = extractor_node(state)

        # 验证无提案
        assert result["pending_proposal"] is None

    @patch('app.agent.nodes.extractor.get_llm')
    def test_llm_error_returns_no_proposal(self, mock_get_llm):
        """测试：LLM 调用失败时不阻断流程"""
        mock_llm = Mock()
        mock_llm.with_structured_output.side_effect = Exception("LLM API Error")
        mock_get_llm.return_value = mock_llm

        state = {
            "messages": [
                {"role": "user", "content": "测试消息"}
            ],
            "user_id": 1
        }

        result = extractor_node(state)

        # 验证无提案，流程继续
        assert result["pending_proposal"] is None


class TestRouterDecision:
    """测试路由决策函数"""

    def test_pending_proposal_intercept_1(self):
        """测试：pending_proposal 存在时，输入 1 路由到 save"""
        state = {
            "messages": [
                {"role": "user", "content": "1"}
            ],
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "测试内容"
            }
        }
        result = router_decision_function(state)
        assert result == "save_asset_node"

    def test_pending_proposal_intercept_0(self):
        """测试：pending_proposal 存在时，输入 0 路由到 discard"""
        state = {
            "messages": [
                {"role": "user", "content": "0"}
            ],
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "测试内容"
            }
        }
        result = router_decision_function(state)
        assert result == "discard_asset_node"

    def test_pending_proposal_other_input_routes_to_extractor(self):
        """测试：pending_proposal 存在时，输入其他内容路由到 extractor（连续上下文模式）"""
        state = {
            "messages": [
                {"role": "user", "content": "太啰嗦了，简洁点"}
            ],
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "测试内容"
            }
        }
        result = router_decision_function(state)
        # 应该路由到 extractor_node 进行调整
        assert result == "extractor_node"

    def test_pending_proposal_refinement_scenario(self):
        """测试：连续上下文场景 - 用户反馈应该路由到调整模式"""
        # 场景：用户输入"太啰嗦了"，应该进入调整模式而不是放弃
        state = {
            "messages": [
                {"role": "user", "content": "太啰嗦了"}
            ],
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "我精通 Python 编程语言"
            }
        }
        result = router_decision_function(state)
        # 连续上下文：任何非 1/0 的输入都视为调整反馈
        assert result == "extractor_node"

    def test_no_proposal_routes_to_extractor(self):
        """测试：无提案时路由到 extractor"""
        state = {
            "messages": [
                {"role": "user", "content": "随便聊聊天"}
            ],
            "pending_proposal": None
        }
        result = router_decision_function(state)
        assert result == "extractor_node"

    def test_resume_refine_intent_routes_to_pruner(self):
        """测试：resume_refine 意图路由到 pruner"""
        state = {
            "messages": [
                {"role": "user", "content": "帮我改简历"}
            ],
            "pending_proposal": None,
            "current_intent": ChatIntent.RESUME_REFINE
        }
        result = router_decision_function(state)
        assert result == "pruner_node"

    def test_interview_prep_intent_routes_to_pruner(self):
        """测试：interview_prep 意图路由到 pruner"""
        state = {
            "messages": [
                {"role": "user", "content": "准备面试"}
            ],
            "pending_proposal": None,
            "current_intent": ChatIntent.INTERVIEW_PREP
        }
        result = router_decision_function(state)
        assert result == "pruner_node"


class TestSaveAssetNode:
    """测试保存资产节点"""

    @patch('app.agent.nodes.db_ops.get_engine')
    @patch('app.agent.nodes.db_ops.ProfileRepository')
    def test_save_asset_to_database(self, mock_repo_class, mock_get_engine):
        """测试：资产保存到数据库"""
        # Mock session and repository
        mock_session = MagicMock()
        mock_engine = Mock()
        mock_get_engine.return_value = mock_engine

        # Mock context manager
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)

        # Mock Session to return our mock_session
        with patch('sqlmodel.Session', return_value=mock_session):
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_by_user_and_key.return_value = None

            state = {
                "pending_proposal": {
                    "section_key": "skills",
                    "refined_content": "我掌握 Python",
                    "thought": "测试推理"
                },
                "user_id": 1,
                "messages": []
            }

            result = save_asset_node(state)

            # 验证清空提案
            assert result["pending_proposal"] is None

            # 验证成功消息
            assert any("已保存" in m["content"] for m in result["messages"])

            # 验证数据库调用
            mock_repo.update_by_user_and_key.assert_called_once()

    def test_save_asset_with_invalid_section_key(self):
        """测试：无效的 section_key 返回错误消息"""
        state = {
            "pending_proposal": {
                "section_key": "invalid_key",
                "refined_content": "测试内容",
                "thought": "测试推理"
            },
            "user_id": 1,
            "messages": []
        }

        result = save_asset_node(state)

        # 验证清空提案
        assert result["pending_proposal"] is None

        # 验证错误消息
        assert any("错误" in m["content"] for m in result["messages"])

    def test_save_asset_with_no_proposal(self):
        """测试：无提案时直接返回"""
        state = {
            "pending_proposal": None,
            "messages": []
        }

        result = save_asset_node(state)

        # 验证无变化
        assert result["pending_proposal"] is None
        assert len(result["messages"]) == 0


class TestDiscardAssetNode:
    """测试丢弃资产节点"""

    def test_discard_asset_clears_proposal(self):
        """测试：丢弃资产清空提案"""
        state = {
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "测试内容"
            },
            "messages": []
        }

        result = discard_asset_node(state)

        # 验证清空提案
        assert result["pending_proposal"] is None

        # 验证丢弃消息
        assert any("已丢弃" in m["content"] for m in result["messages"])

    def test_discard_asset_with_empty_messages(self):
        """测试：空消息列表时丢弃资产"""
        state = {
            "pending_proposal": {
                "section_key": "skills",
                "refined_content": "测试内容"
            },
            "messages": []
        }

        result = discard_asset_node(state)

        # 验证清空提案
        assert result["pending_proposal"] is None

        # 验证添加了丢弃消息
        assert len(result["messages"]) == 1
        assert "已丢弃" in result["messages"][0]["content"]


class TestGraphIntegration:
    """测试图集成 (简单流程验证)"""

    def test_graph_can_be_created(self):
        """测试：工作流图可以正常创建"""
        from app.agent.graph import create_agent_graph

        graph = create_agent_graph()
        assert graph is not None

    def test_default_agent_state_includes_new_fields(self):
        """测试：默认 AgentState 包含新增字段"""
        from app.agent.state import DEFAULT_AGENT_STATE

        assert "pending_proposal" in DEFAULT_AGENT_STATE
        assert DEFAULT_AGENT_STATE["pending_proposal"] is None
        assert "user_id" in DEFAULT_AGENT_STATE
        assert DEFAULT_AGENT_STATE["user_id"] == 1


class TestProfileSectionKeyEnum:
    """测试 ProfileSectionKey 枚举扩展"""

    def test_career_potential_enum_exists(self):
        """测试：CAREER_POTENTIAL 枚举值存在"""
        assert hasattr(ProfileSectionKey, 'CAREER_POTENTIAL')
        assert ProfileSectionKey.CAREER_POTENTIAL.value == "career_potential"

    def test_all_enum_values_are_valid(self):
        """测试：所有枚举值都有正确的字符串值"""
        expected_values = {
            "skills",
            "work_experience",
            "projects_summary",
            "project_details",
            "behavioral_traits",
            "education",
            "summary",
            "career_potential"  # T2-01.2 新增
        }

        actual_values = {key.value for key in ProfileSectionKey}
        assert actual_values == expected_values
