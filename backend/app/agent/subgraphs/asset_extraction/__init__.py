"""
资产提取子图模块

该子图封装了隐性资产提取的完整流程：
1. 提取器节点分析用户消息
2. 路由决策判断是否有待确认的提案
3. 用户确认后保存，或拒绝后丢弃

使用示例:
    from app.agent.subgraphs.asset_extraction import create_asset_extraction_subgraph

    # 在主图中添加子图
    subgraph = create_asset_extraction_subgraph()
    workflow.add_node("asset_extraction", subgraph)
"""

# TODO: 待实现 create_asset_extraction_subgraph
# from app.agent.subgraphs.asset_extraction.asset_extraction_subgraph import (
#     create_asset_extraction_subgraph,
#     asset_extraction_subgraph,
# )

__all__ = [
    # "create_asset_extraction_subgraph",
    # "asset_extraction_subgraph",
]
