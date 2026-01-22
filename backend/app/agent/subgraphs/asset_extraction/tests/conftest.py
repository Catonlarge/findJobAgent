"""
Asset Extraction 子图测试配置

提供 Mock LLM、测试状态等测试基础设施
"""

import pytest
from unittest.mock import Mock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph.state import RunnableConfig
from sqlmodel import Session

from app.agent.models import ProfilerOutput, SingleObservation
from app.db.init_db import get_engine
from app.models import User


@pytest.fixture(scope="function")
def test_user():
    """
    创建测试用户（每个测试函数使用唯一的用户名）
    """
    import uuid
    engine = get_engine()
    with Session(engine) as session:
        # 使用唯一的用户名避免冲突
        unique_username = f"test_user_{uuid.uuid4().hex[:8]}"
        user = User(username=unique_username, basic_info={"name": "测试用户", "city": "Beijing"})
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture(scope="function")
def mock_runnable_config():
    """
    Mock LangGraph RunnableConfig

    模拟包含 username 的配置
    """
    return {
        "configurable": {
            "username": "test_user",
            "user_id": "test_user",
            "thread_id": "test_thread_123"
        }
    }


@pytest.fixture(scope="function")
def mock_chat_state():
    """
    Mock ChatAndProfileState 基础状态
    """
    return {
        "messages": [],
        "l1_observations_summary": "",
        "last_turn_analysis": None,
        "session_new_observation_count": 0,
        "last_user_message": None
    }


@pytest.fixture(scope="function")
def mock_editor_state():
    """
    Mock EditorState 基础状态
    """
    return {
        "messages": [],
        "raw_materials": [],
        "current_drafts": [],
        "active_index": 0
    }


@pytest.fixture(scope="function")
def sample_human_message():
    """
    示例用户消息
    """
    msg = HumanMessage(content="我会 Python 和 FastAPI，做过几个后端项目")
    msg.id = "msg_uuid_123"
    return msg


@pytest.fixture(scope="function")
def sample_observations():
    """
    示例观察数据列表
    """
    return [
        {
            "category": "skills",
            "fact_content": "掌握 Python 编程语言",
            "confidence": 0.9,
            "is_potential_signal": False
        },
        {
            "category": "skills",
            "fact_content": "熟悉 FastAPI 框架",
            "confidence": 0.85,
            "is_potential_signal": False
        },
        {
            "category": "experience",
            "fact_content": "有后端开发经验",
            "confidence": 0.8,
            "is_potential_signal": False
        }
    ]


@pytest.fixture(scope="function")
def mock_profiler_output():
    """
    Mock Profiler 结构化输出
    """
    from app.models.observation import ObservationCategory
    return ProfilerOutput(
        analysis_summary="用户提到了 Python 和 FastAPI 技能",
        observations=[
            SingleObservation(
                category=ObservationCategory.SKILL,
                fact_content="掌握 Python 编程语言",
                confidence=90,
                is_potential_signal=False
            ),
            SingleObservation(
                category=ObservationCategory.SKILL,
                fact_content="熟悉 FastAPI 框架",
                confidence=85,
                is_potential_signal=False
            )
        ],
        duplicates_found=[]
    )


@pytest.fixture(scope="function")
def mock_llm_for_chat():
    """
    Mock LLM 用于聊天节点
    """
    mock = Mock()
    mock.invoke.return_value = AIMessage(
        content="听起来你的技术栈很扎实！Python 和 FastAPI 都是现代后端开发的热门选择。"
    )
    return mock


@pytest.fixture(scope="function")
def mock_llm_for_profiler(mock_profiler_output):
    """
    Mock 结构化输出 LLM 用于 Profiler 节点
    """
    mock = Mock()
    mock_structured = Mock()
    mock_structured.invoke.return_value = mock_profiler_output
    mock.with_structured_output.return_value = mock_structured
    return mock
