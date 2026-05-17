"""NovelState 状态机定义：LangGraph 全局 State TypedDict"""

from typing import TypedDict


class NovelState(TypedDict):
    """LangGraph 6Agent 共享的全局状态"""

    # 基础配置
    user_config: dict
    project_id: str

    # 大纲体系
    full_outline: dict
    chapter_outline: list

    # 创作进度
    current_volume: int
    current_chapter: int

    # 章节内容
    chapter_title: str
    chapter_content: str
    chapter_summary: str

    # 全局记忆
    global_scroll_summary: str
    character_status: dict

    # 剧情审核结果
    audit_result: bool
    audit_opinion: str

    # 版权审核结果
    copyright_score: float
    copyright_similarity: float
    copyright_opinion: str
    copyright_pass: bool

    # 流程控制
    step: str
    error_info: str
    rewrite_times: int
