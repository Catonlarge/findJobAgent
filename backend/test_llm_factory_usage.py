#!/usr/bin/env python
"""示例：使用 LLMFactory 获取 LLM 实例

这个脚本演示如何使用 LLMFactory 来创建和测试 LLM 实例。
需要确保环境变量已设置：
- 如果使用 moonshot 模型：MOONSHOT_API_KEY
- 如果使用 gemini 模型：GEMINI_API_KEY
- 如果使用 openai_official 模型：OPENAI_API_KEY
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.llm_factory import LLMFactory, get_llm


def test_factory_basic():
    """测试基本的工厂功能"""
    print("=" * 60)
    print("测试 1: 创建 LLMFactory 实例")
    print("=" * 60)

    factory = LLMFactory()  # 使用默认的 llm_config.json
    print("✓ LLMFactory 实例创建成功")

    # 获取激活的模型配置
    config = factory.get_active_model_config()
    print(f"✓ 当前激活模型配置: {config}")

    # 尝试获取 API key (这会失败如果没有设置环境变量)
    try:
        llm = factory.create_llm()
        print(f"✓ LLM 实例创建成功: {type(llm).__name__}")
    except ValueError as e:
        print(f"✗ 无法创建 LLM: {e}")
        print("  请确保已设置对应的环境变量")


def test_get_llm_function():
    """测试 get_llm 便捷函数"""
    print("\n" + "=" * 60)
    print("测试 2: 使用 get_llm() 便捷函数")
    print("=" * 60)

    try:
        llm = get_llm()
        print(f"✓ LLM 实例创建成功: {type(llm).__name__}")
    except ValueError as e:
        print(f"✗ 无法创建 LLM: {e}")
        print("  请确保已设置对应的环境变量")


def show_current_config():
    """显示当前配置"""
    print("\n" + "=" * 60)
    print("当前 LLM 配置信息")
    print("=" * 60)

    factory = LLMFactory()
    config = factory.get_active_model_config()

    print(f"激活的模型: {factory._load_config()['active_model']}")
    print(f"模型名称: {config.get('model_name')}")
    print(f"所需环境变量: {config.get('env_key_map')}")
    print(f"基础 URL: {config.get('base_url', 'N/A')}")
    print(f"Temperature: {config.get('temperature')}")

    # 检查环境变量是否已设置
    env_key = config.get('env_key_map')
    if env_key:
        api_key = os.getenv(env_key)
        if api_key:
            print(f"✓ {env_key}: 已设置 (长度: {len(api_key)})")
        else:
            print(f"✗ {env_key}: 未设置")


def main():
    """主函数"""
    print("LLMFactory 使用示例")
    print("====================")

    try:
        # 显示当前配置
        show_current_config()

        # 测试工厂基本功能
        test_factory_basic()

        # 测试便捷函数
        test_get_llm_function()

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
