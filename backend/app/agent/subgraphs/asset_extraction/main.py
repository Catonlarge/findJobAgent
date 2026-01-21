"""
人生说明书编辑器 - 主循环入口

这是 T2-01.2 任务的主入口，实现了以下功能：
1. 数据库初始化（默认用户、画像切片、会话）
2. 资产提取子图的加载
3. 主循环：接收用户输入 -> 存储消息 -> 调用子图 -> 流式输出 -> 循环

架构参考：docs/detailedDevPlan/lifeManual.md

使用示例：
    python -m app.agent.subgraphs.asset_extraction.main
"""

import sys
import os
import uuid

# 确保项目根目录在 Python 路径中
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langgraph.checkpoint.memory import MemorySaver

from app.db.init_db import init_db
from app.services.chat_service import ChatService
from app.agent.subgraphs.asset_extraction import create_asset_extraction_subgraph


def print_banner():
    """打印欢迎横幅"""
    print("=" * 60)
    print("  人生说明书编辑器 V7.2")
    print("  - 双层数据流：L1 静默记录 + L2 用户确认")
    print("  - 游标循环：批量提案 -> 单件精修 -> 即时存档")
    print("=" * 60)
    print()


def main():
    """
    主循环函数

    流程：
    1. 初始化数据库（表结构 + 默认数据）
    2. 初始化 ChatService（身份锚定 + 会话容器保证）
    3. 加载资产提取子图（配置 MemorySaver checkpointer）
    4. 循环：用户输入 -> 流式输出 -> 继续
    """
    # 1. 数据库初始化
    print("\n[Main] 正在初始化数据库...")
    init_db()

    # 2. 配置用户和会话标识
    username = "me"  # 默认用户名
    session_uuid = str(uuid.uuid4())  # 生成会话 UUID（thread_id 等于此值）

    # 3. 初始化 ChatService
    print(f"\n[Main] 正在初始化 ChatService...")
    chat_service = ChatService(username=username, session_uuid=session_uuid)

    # 4. 加载资产提取子图（配置 checkpointer）
    print("[Main] 正在加载资产提取子图...")
    checkpointer = MemorySaver()
    asset_extraction_graph = create_asset_extraction_subgraph(checkpointer=checkpointer)
    print("[Main] 资产提取子图加载完成（已启用 MemorySaver checkpointer）\n")

    # 5. 打印欢迎信息
    print_banner()
    print("提示：输入 'quit' 或 'exit' 退出程序")
    print("      输入 'edit' 触发整理模式（生成资产提案）")
    print()

    # 6. 主循环
    while True:
        try:
            # 获取用户输入
            user_input = input("You: ").strip()

            # 退出命令
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n[Main] 再见！")
                break

            # 跳过空输入
            if not user_input:
                continue

            # 触发整理模式
            if user_input.lower() == "edit":
                print("\n[Main] 触发整理模式...")
                print("[Main] 正在从数据库加载 pending 状态的观察记录...")
                # 整理模式会通过子图内部的 editor_loader_node 自动触发
                user_input = "请帮我整理一下目前的档案"

            # 7. 调用服务发送消息
            print("AI: ", end="", flush=True)
            response_full = ""

            for chunk in chat_service.send_message_stream(user_input, asset_extraction_graph):
                print(chunk, end="", flush=True)
                response_full = chunk

            print()  # 换行
            print()

        except KeyboardInterrupt:
            print("\n\n[Main] 收到中断信号，正在退出...")
            break
        except Exception as e:
            print(f"\n[Main Error] {str(e)}")
            import traceback
            traceback.print_exc()
            print()


if __name__ == "__main__":
    main()
