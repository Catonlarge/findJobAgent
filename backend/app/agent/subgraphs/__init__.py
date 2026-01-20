"""
子图模块

该模块包含 LangGraph 子图定义，用于封装复杂的多节点工作流。
子图可以被主图引用，实现工作流的模块化和复用。

目录结构:
    subgraphs/
    ├── asset_extraction/         # 资产提取子图（目录模式，包含专属节点）
    │   ├── __init__.py
    │   ├── asset_extraction.py   # 子图定义
    │   └── extractor.py          # 专属提取器节点
    ├── resume_refine.py          # 简历优化子图（单文件模式）
    └── interview_prep.py         # 面试准备子图（单文件模式）

使用示例:
    from app.agent.subgraphs import (
        create_asset_extraction_subgraph,
        create_resume_refine_subgraph,
        create_interview_prep_subgraph,
    )

    # 在主图中添加子图
    asset_subgraph = create_asset_extraction_subgraph()
    workflow.add_node("asset_extraction", asset_subgraph)
"""

from app.agent.subgraphs.asset_extraction import (
    create_asset_extraction_subgraph,
    asset_extraction_subgraph,
)
from app.agent.subgraphs.resume_refine import (
    create_resume_refine_subgraph,
    resume_refine_subgraph,
)
from app.agent.subgraphs.interview_prep import (
    create_interview_prep_subgraph,
    interview_prep_subgraph,
)

__all__ = [
    "create_asset_extraction_subgraph",
    "asset_extraction_subgraph",
    "create_resume_refine_subgraph",
    "resume_refine_subgraph",
    "create_interview_prep_subgraph",
    "interview_prep_subgraph",
]
