"""摘要Agent：生成单章摘要、更新全局滚动摘要、Embedding入库"""

from ..core.llm import call_llm
from ..utils.logger import get_logger

logger = get_logger(__name__)


async def generate_summary(
    chapter_content: str,
    chapter_number: int,
) -> dict:
    """生成章节摘要，提取关键信息"""
    system_prompt = """你是一位小说摘要专家。根据章节内容生成结构化摘要。

摘要要求：
- 提取本章关键剧情（3-5个要点）
- 提取人物变化和状态更新
- 提取新增伏笔和悬念
- 提取势力变动
- 总字数控制在300字以内
- 使用中文"""

    user_prompt = f"""第{chapter_number}章内容：
{chapter_content}

请生成结构化摘要。"""

    try:
        summary = await call_llm(system_prompt, user_prompt)
        return {
            "summary": summary,
            "key_events": [],  # 实际应解析提取
            "character_changes": [],
            "foreshadowing": [],
        }
    except Exception as e:
        logger.error(f"摘要生成失败: {e}", exc_info=True)
        raise


async def update_global_summary(
    current_summary: str,
    new_chapter_summary: str,
    chapter_number: int,
) -> str:
    """更新全局滚动摘要（最近5章浓缩）"""
    system_prompt = """你是一位小说记忆管理专家。将新章节摘要合并到全局滚动摘要中。

要求：
- 保留最近5章的关键信息
- 压缩早期章节为一两句话
- 确保剧情连贯性
- 总字数控制在500字以内"""

    user_prompt = f"""当前全局摘要：
{current_summary}

第{chapter_number}章新摘要：
{new_chapter_summary}

请更新全局滚动摘要。"""

    try:
        updated = await call_llm(system_prompt, user_prompt)
        return updated
    except Exception as e:
        logger.error(f"全局摘要更新失败: {e}", exc_info=True)
        return current_summary
