"""LLM 工厂模块

根据配置文件创建和管理 LLM 实例。
遵循安全协议：从不读取 .env 文件，只从系统环境变量获取密钥。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


class LLMFactory:
    """LLM 工厂类，负责创建和管理 LLM 实例"""

    def __init__(self, config_path: str = None):
        """初始化工厂，加载配置文件

        Args:
            config_path: 配置文件路径，如果为 None 则使用相对于项目根目录的默认路径
        """
        if config_path is None:
            # 默认路径：从 backend/app/agent/llm_factory.py 到 backend/llm_config.json
            default_path = Path(__file__).parent.parent.parent / "llm_config.json"
            self.config_path = str(default_path)
        else:
            self.config_path = config_path
        self._config = None
        self._loaded_config = None

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: JSON 格式错误
        """
        if self._loaded_config is None:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._loaded_config = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(f"JSON 格式错误: {e}", e.doc, e.pos)

        return self._loaded_config

    def get_active_model_config(self) -> Dict[str, Any]:
        """获取当前激活的模型配置

        Returns:
            当前激活模型的配置字典

        Raises:
            KeyError: 配置结构错误
            ValueError: active_model 不存在或对应的 provider 配置不存在
        """
        config = self._load_config()

        # 获取 active_model
        active_model = config.get("active_model")
        if not active_model:
            raise ValueError("配置文件中缺少 active_model 字段")

        # 获取 providers 配置
        providers = config.get("providers")
        if not providers:
            raise ValueError("配置文件中缺少 providers 字段")

        # 获取对应模型的配置
        model_config = providers.get(active_model)
        if not model_config:
            raise ValueError(f"providers 中找不到 '{active_model}' 的配置")

        return model_config

    def _get_api_key(self, env_key: str) -> str:
        """从系统环境变量获取 API Key

        Args:
            env_key: 环境变量名

        Returns:
            API Key 字符串

        Raises:
            ValueError: 环境变量不存在或为空
        """
        api_key = os.getenv(env_key)
        if not api_key:
            raise ValueError(f"环境变量 '{env_key}' 未设置或为空，无法初始化 LLM")

        return api_key

    def create_llm(self) -> Any:
        """创建并返回 LLM 实例

        Returns:
            LangChain LLM 对象 (ChatOpenAI 或 ChatGoogleGenerativeAI)

        Raises:
            ValueError: 配置错误或环境变量缺失
            NotImplementedError: 不支持的模型类型
        """
        # 获取当前激活模型的配置
        model_config = self.get_active_model_config()

        # 获取环境变量映射
        env_key_map = model_config.get("env_key_map")
        if not env_key_map:
            raise ValueError("模型配置中缺少 env_key_map 字段")

        # 从环境变量获取 API Key
        api_key = self._get_api_key(env_key_map)

        # 获取其他配置参数
        base_url = model_config.get("base_url")
        model_name = model_config.get("model_name")
        temperature = model_config.get("temperature", 0.7)

        if not model_name:
            raise ValueError("模型配置中缺少 model_name 字段")

        # 根据 active_model 创建对应的 LLM 实例
        active_model = self._load_config()["active_model"]

        if active_model == "moonshot":
            # Moonshot 使用 OpenAI 兼容接口
            return ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model_name,
                temperature=temperature
            )
        elif active_model == "gemini":
            # Google Gemini
            return ChatGoogleGenerativeAI(
                google_api_key=api_key,
                model=model_name,
                temperature=temperature
            )
        elif active_model == "openai_official":
            # OpenAI 官方
            return ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model_name,
                temperature=temperature
            )
        else:
            raise NotImplementedError(f"不支持的模型类型: {active_model}")


# 全局工厂实例
llm_factory = LLMFactory()


def get_llm():
    """获取 LLM 实例的便捷函数

    Returns:
        LangChain LLM 对象
    """
    return llm_factory.create_llm()
