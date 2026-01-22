"""
Utils 工具函数测试

测试 asset_extraction 子图中的工具函数：
1. should_save_observation: 质量检查
2. save_observation_to_l1: 保存观察到 L1
3. save_observation_from_dict: 从字典保存观察
4. get_existing_observations_summary: 获取观察摘要
"""

import pytest
from sqlmodel import Session, select

from app.agent.subgraphs.asset_extraction.utils import (
    should_save_observation,
    save_observation_to_l1,
    save_observation_from_dict,
    get_existing_observations_summary,
)
from app.models.observation import ObservationCategory, ObservationStatus, RawObservation
from app.db.init_db import init_db, get_engine


class TestShouldSaveObservation:
    """测试 should_save_observation 质量检查函数"""

    def test_valid_content_passes(self):
        """测试有效内容通过检查"""
        assert should_save_observation("掌握 Python 编程语言") is True
        assert should_save_observation("喜欢阅读科技类书籍") is True

    def test_empty_content_fails(self):
        """测试空内容未通过检查"""
        assert should_save_observation("") is False
        assert should_save_observation("   ") is False
        assert should_save_observation("太短") is False

    def test_min_length_threshold(self):
        """测试最小长度阈值"""
        # 默认阈值是 5
        assert should_save_observation("1234") is False
        assert should_save_observation("12345") is True

    def test_custom_min_length(self):
        """测试自定义最小长度"""
        # "短内容" 长度是 3，小于阈值 10
        assert should_save_observation("短内容", min_length=10) is False
        # "这是一个较长的内容" 长度是 9，strip 后长度仍是 9，小于阈值 10
        # 需要提供更长的内容
        assert should_save_observation("这是一个足够长的内容用于测试", min_length=10) is True


class TestSaveObservationToL1:
    """测试 save_observation_to_l1 保存函数"""

    def test_save_valid_observation(self, test_user):
        """测试保存有效观察"""
        success = save_observation_to_l1(
            user_id=test_user.id,
            category=ObservationCategory.SKILL,
            fact_content="掌握 Python 编程语言",
            confidence=90,
            is_potential_signal=False,
            reasoning="用户明确提到了编程技能",
            source_msg_uuid="test-uuid-123",
            source_message_count=1,
            enable_quality_check=True
        )

        assert success is True

        # 验证数据库中的记录
        engine = get_engine()
        with Session(engine) as session:
            statement = select(RawObservation).where(
                RawObservation.user_id == test_user.id
            )
            results = session.exec(statement).all()
            assert len(results) == 1

            obs = results[0]
            assert obs.category == ObservationCategory.SKILL
            assert obs.fact_content == "掌握 Python 编程语言"
            assert obs.confidence == 90
            assert obs.is_potential_signal is False
            assert obs.status == ObservationStatus.PENDING
            assert obs.source_msg_uuid == "test-uuid-123"

    def test_save_observation_without_quality_check(self, test_user):
        """测试跳过质量检查"""
        # 内容过短，但跳过质量检查
        success = save_observation_to_l1(
            user_id=test_user.id,
            category=ObservationCategory.TRAIT,
            fact_content="短",  # 低于默认阈值 5
            confidence=50,
            is_potential_signal=False,
            reasoning="测试用",
            enable_quality_check=False  # 跳过质量检查
        )

        assert success is True

    def test_save_observation_with_quality_check_fails(self, test_user):
        """测试质量检查失败"""
        # 内容过短，启用质量检查
        success = save_observation_to_l1(
            user_id=test_user.id,
            category=ObservationCategory.TRAIT,
            fact_content="短",  # 低于默认阈值 5
            confidence=50,
            is_potential_signal=False,
            reasoning="测试用",
            enable_quality_check=True  # 启用质量检查
        )

        assert success is False

    def test_save_all_categories(self, test_user):
        """测试保存所有分类的观察"""
        categories_and_contents = [
            (ObservationCategory.SKILL, "熟练使用 Git 版本控制"),
            (ObservationCategory.TRAIT, "注重细节，追求完美"),
            (ObservationCategory.EXPERIENCE, "曾在初创公司担任全栈工程师"),
            (ObservationCategory.PREFERENCE, "偏好远程工作，希望有灵活时间"),
        ]

        for category, content in categories_and_contents:
            success = save_observation_to_l1(
                user_id=test_user.id,
                category=category,
                fact_content=content,
                confidence=80,
                is_potential_signal=False,
                reasoning="测试用"
            )
            assert success is True

        # 验证所有分类都已保存
        engine = get_engine()
        with Session(engine) as session:
            statement = select(RawObservation).where(
                RawObservation.user_id == test_user.id
            )
            results = session.exec(statement).all()
            assert len(results) == 4


class TestSaveObservationFromDict:
    """测试 save_observation_from_dict 从字典保存函数"""

    def test_save_from_dict_valid_category(self, test_user):
        """测试使用有效的 category 字符串保存"""
        success = save_observation_from_dict(
            user_id=test_user.id,
            category="skill_detect",
            fact_content="掌握 Python 编程语言",
            confidence=90,
            is_potential_signal=False,
            reasoning="测试用"
        )

        assert success is True

        # 验证数据库中的记录
        engine = get_engine()
        with Session(engine) as session:
            statement = select(RawObservation).where(
                RawObservation.user_id == test_user.id
            )
            results = session.exec(statement).all()
            assert len(results) == 1
            assert results[0].category == ObservationCategory.SKILL

    def test_save_from_dict_invalid_category(self, test_user):
        """测试使用无效的 category 字符串"""
        success = save_observation_from_dict(
            user_id=test_user.id,
            category="invalid_category",  # 无效的分类
            fact_content="测试内容",
            confidence=50,
            is_potential_signal=False,
            reasoning="测试用"
        )

        assert success is False

    def test_save_from_dict_all_categories(self, test_user):
        """测试所有分类的字符串映射"""
        category_strings = [
            "skill_detect",
            "trait_detect",
            "experience_fragment",
            "preference"
        ]

        for cat_str in category_strings:
            success = save_observation_from_dict(
                user_id=test_user.id,
                category=cat_str,
                fact_content=f"测试 {cat_str}",
                confidence=70,
                is_potential_signal=False,
                reasoning="测试用"
            )
            assert success is True

        # 验证所有分类都已保存
        engine = get_engine()
        with Session(engine) as session:
            statement = select(RawObservation).where(
                RawObservation.user_id == test_user.id
            )
            results = session.exec(statement).all()
            assert len(results) == 4


class TestGetExistingObservationsSummary:
    """测试 get_existing_observations_summary 获取摘要函数"""

    def test_no_existing_observations(self, test_user):
        """测试用户没有观察记录时的返回"""
        summary, has_existing = get_existing_observations_summary(test_user.id)

        assert has_existing is False
        assert "暂无" in summary

    def test_with_existing_observations(self, test_user):
        """测试获取已有观察的摘要"""
        # 先创建一些观察记录（内容长度 >= 5 以通过质量检查）
        observations = [
            (ObservationCategory.SKILL, "掌握 Python 编程语言"),
            (ObservationCategory.SKILL, "熟悉 Django 框架"),
            (ObservationCategory.TRAIT, "非常注重细节和代码质量"),
            (ObservationCategory.EXPERIENCE, "曾在互联网公司工作"),
            (ObservationCategory.PREFERENCE, "偏好远程工作模式"),
        ]

        for category, content in observations:
            save_observation_to_l1(
                user_id=test_user.id,
                category=category,
                fact_content=content,
                confidence=80,
                is_potential_signal=False,
                reasoning="测试用"
            )

        # 获取摘要
        summary, has_existing = get_existing_observations_summary(test_user.id)

        assert has_existing is True
        assert "Skill" in summary or "skill_detect" in summary
        assert "Python" in summary
        assert "Django" in summary
        assert "细节" in summary or "质量" in summary

    def test_max_per_category_limit(self, test_user):
        """测试每个分类的最大数量限制"""
        # 创建超过限制的观察（每个分类 3 条，限制 2 条）
        # 注意：内容长度必须 >= 5 以通过质量检查
        for i in range(3):
            save_observation_to_l1(
                user_id=test_user.id,
                category=ObservationCategory.SKILL,
                fact_content=f"这是一条测试技能内容 {i+1}",
                confidence=80,
                is_potential_signal=False,
                reasoning="测试用"
            )

        # 获取摘要，限制每个分类 2 条
        summary, has_existing = get_existing_observations_summary(
            test_user.id,
            max_per_category=2
        )

        assert has_existing is True
        # 应该只包含最近的 2 条（技能 2 和技能 3）
        assert "测试技能内容 2" in summary or "测试技能内容 3" in summary
        # 验证限制生效：应该只包含 2 条，不包含第 1 条
        assert "测试技能内容 1" not in summary

    def test_summary_format(self, test_user):
        """测试摘要格式是否正确"""
        save_observation_to_l1(
            user_id=test_user.id,
            category=ObservationCategory.SKILL,
            fact_content="Python 开发",
            confidence=90,
            is_potential_signal=False,
            reasoning="测试用"
        )

        summary, has_existing = get_existing_observations_summary(test_user.id)

        assert has_existing is True
        # 检查格式：应该包含分类标题和列表项
        assert "**" in summary  # 分类标题使用 markdown 加粗
        assert "  - " in summary  # 列表项缩进
