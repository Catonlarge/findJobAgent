"""测试 LLM 工厂模块"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, Mock

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent.parent
import sys
sys.path.insert(0, str(project_root))

from app.agent.llm_factory import LLMFactory, get_llm
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


class TestLLMFactory:
    """测试 LLMFactory 类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.test_config = {
            "active_model": "moonshot",
            "providers": {
                "moonshot": {
                    "base_url": "https://api.moonshot.cn/v1",
                    "model_name": "kimi-k2-turbo-preview",
                    "env_key_map": "MOONSHOT_API_KEY",
                    "temperature": 0.6
                },
                "gemini": {
                    "base_url": None,
                    "model_name": "gemini-2.5-flash",
                    "env_key_map": "GEMINI_API_KEY",
                    "temperature": 0.7
                },
                "openai_official": {
                    "base_url": "https://api.openai.com/v1",
                    "model_name": "gpt-4-turbo",
                    "env_key_map": "OPENAI_API_KEY",
                    "temperature": 0.6
                }
            }
        }
        self.config_path = "test_llm_config.json"

        # 创建测试配置文件
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.test_config, f)

        self.factory = LLMFactory(self.config_path)

    def teardown_method(self):
        """每个测试方法后的清理"""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_load_config_success(self):
        """测试成功加载配置文件"""
        config = self.factory._load_config()
        assert config == self.test_config
        assert config["active_model"] == "moonshot"

    def test_load_config_file_not_found(self):
        """测试配置文件不存在时的错误处理"""
        factory = LLMFactory("nonexistent_config.json")
        with pytest.raises(FileNotFoundError) as exc_info:
            factory._load_config()
        assert "配置文件不存在" in str(exc_info.value)

    def test_load_config_invalid_json(self):
        """测试 JSON 格式错误时的处理"""
        invalid_config_path = "invalid_config.json"
        with open(invalid_config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json}")

        factory = LLMFactory(invalid_config_path)
        with pytest.raises(json.JSONDecodeError):
            factory._load_config()

        os.remove(invalid_config_path)

    def test_get_active_model_config_success(self):
        """测试成功获取当前激活模型配置"""
        model_config = self.factory.get_active_model_config()
        assert model_config["model_name"] == "kimi-k2-turbo-preview"
        assert model_config["env_key_map"] == "MOONSHOT_API_KEY"
        assert model_config["temperature"] == 0.6

    def test_get_active_model_config_missing_active_model(self):
        """测试配置文件缺少 active_model 字段"""
        config_without_active = {"providers": {}}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_without_active, f)

        factory = LLMFactory(self.config_path)
        with pytest.raises(ValueError) as exc_info:
            factory.get_active_model_config()
        assert "缺少 active_model" in str(exc_info.value)

    def test_get_active_model_config_missing_providers(self):
        """测试配置文件缺少 providers 字段"""
        config_without_providers = {"active_model": "moonshot"}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_without_providers, f)

        factory = LLMFactory(self.config_path)
        with pytest.raises(ValueError) as exc_info:
            factory.get_active_model_config()
        assert "缺少 providers" in str(exc_info.value)

    def test_get_active_model_config_model_not_found(self):
        """测试 active_model 对应的 provider 不存在"""
        config_with_wrong_model = {
            "active_model": "nonexistent",
            "providers": {"moonshot": {}}
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_with_wrong_model, f)

        factory = LLMFactory(self.config_path)
        with pytest.raises(ValueError) as exc_info:
            factory.get_active_model_config()
        assert "找不到 'nonexistent' 的配置" in str(exc_info.value)

    def test_get_api_key_success(self):
        """测试成功从环境变量获取 API Key"""
        with patch.dict(os.environ, {"TEST_API_KEY": "test-key-123"}):
            api_key = self.factory._get_api_key("TEST_API_KEY")
            assert api_key == "test-key-123"

    def test_get_api_key_not_set(self):
        """测试环境变量未设置时的错误处理"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                self.factory._get_api_key("NONEXISTENT_KEY")
            assert "环境变量 'NONEXISTENT_KEY' 未设置" in str(exc_info.value)

    def test_get_api_key_empty(self):
        """测试环境变量为空字符串时的错误处理"""
        with patch.dict(os.environ, {"EMPTY_KEY": ""}):
            with pytest.raises(ValueError) as exc_info:
                self.factory._get_api_key("EMPTY_KEY")
            assert "环境变量 'EMPTY_KEY' 未设置或为空" in str(exc_info.value)

    @patch("app.agent.llm_factory.ChatOpenAI")
    def test_create_llm_moonshot(self, mock_chat_openai):
        """测试创建 Moonshot (OpenAI 兼容) LLM"""
        mock_instance = Mock(spec=ChatOpenAI)
        mock_chat_openai.return_value = mock_instance

        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "moonshot-key-123"}):
            llm = self.factory.create_llm()

            mock_chat_openai.assert_called_once_with(
                api_key="moonshot-key-123",
                base_url="https://api.moonshot.cn/v1",
                model="kimi-k2-turbo-preview",
                temperature=0.6
            )
            assert llm == mock_instance

    @patch("app.agent.llm_factory.ChatGoogleGenerativeAI")
    def test_create_llm_gemini(self, mock_chat_google):
        """测试创建 Gemini LLM"""
        # 修改配置文件为 gemini
        self.test_config["active_model"] = "gemini"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.test_config, f)

        mock_instance = Mock(spec=ChatGoogleGenerativeAI)
        mock_chat_google.return_value = mock_instance

        with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-key-456"}):
            factory = LLMFactory(self.config_path)
            llm = factory.create_llm()

            mock_chat_google.assert_called_once_with(
                google_api_key="gemini-key-456",
                model="gemini-2.5-flash",
                temperature=0.7
            )
            assert llm == mock_instance

    @patch("app.agent.llm_factory.ChatOpenAI")
    def test_create_llm_openai_official(self, mock_chat_openai):
        """测试创建 OpenAI 官方 LLM"""
        # 修改配置文件为 openai_official
        self.test_config["active_model"] = "openai_official"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.test_config, f)

        mock_instance = Mock(spec=ChatOpenAI)
        mock_chat_openai.return_value = mock_instance

        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key-789"}):
            factory = LLMFactory(self.config_path)
            llm = factory.create_llm()

            mock_chat_openai.assert_called_once_with(
                api_key="openai-key-789",
                base_url="https://api.openai.com/v1",
                model="gpt-4-turbo",
                temperature=0.6
            )
            assert llm == mock_instance

    def test_create_llm_missing_env_key_map(self):
        """测试模型配置缺少 env_key_map 字段"""
        config_without_key_map = {
            "active_model": "moonshot",
            "providers": {
                "moonshot": {
                    "base_url": "https://api.moonshot.cn/v1",
                    "model_name": "kimi-k2-turbo-preview",
                    "temperature": 0.6
                }
            }
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_without_key_map, f)

        factory = LLMFactory(self.config_path)
        with pytest.raises(ValueError) as exc_info:
            factory.create_llm()
        assert "缺少 env_key_map 字段" in str(exc_info.value)

    def test_create_llm_missing_model_name(self):
        """测试模型配置缺少 model_name 字段"""
        config_without_model_name = {
            "active_model": "moonshot",
            "providers": {
                "moonshot": {
                    "base_url": "https://api.moonshot.cn/v1",
                    "env_key_map": "MOONSHOT_API_KEY",
                    "temperature": 0.6
                }
            }
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_without_model_name, f)

        factory = LLMFactory(self.config_path)
        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "test-key"}):
            with pytest.raises(ValueError) as exc_info:
                factory.create_llm()
            assert "缺少 model_name 字段" in str(exc_info.value)

    def test_create_llm_unsupported_model(self):
        """测试不支持的模型类型"""
        config_with_unsupported = {
            "active_model": "unsupported_model",
            "providers": {
                "unsupported_model": {
                    "env_key_map": "UNSUPPORTED_KEY",
                    "model_name": "unsupported"
                }
            }
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_with_unsupported, f)

        factory = LLMFactory(self.config_path)
        with patch.dict(os.environ, {"UNSUPPORTED_KEY": "test-key"}):
            with pytest.raises(NotImplementedError) as exc_info:
                factory.create_llm()
            assert "不支持的模型类型" in str(exc_info.value)

    @patch("app.agent.llm_factory.ChatOpenAI")
    def test_get_llm_function(self, mock_chat_openai):
        """测试便捷函数 get_llm"""
        mock_instance = Mock(spec=ChatOpenAI)
        mock_chat_openai.return_value = mock_instance

        with patch.dict(os.environ, {"MOONSHOT_API_KEY": "moonshot-key-123"}):
            # 测试时使用测试配置文件路径
            test_llm_factory = LLMFactory(self.config_path)
            llm = test_llm_factory.create_llm()

            assert llm == mock_instance
            mock_chat_openai.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
