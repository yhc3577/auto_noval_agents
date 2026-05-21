"""摘要Agent：生成单章摘要、更新全局滚动摘要、Embedding入库（prompt 模板可配置）"""

import json
import re

from ..core.llm import call_llm
from ..services.prompt_service import format_prompt
from ..utils.logger import get_logger

# 匹配 <think>...</think> 及其变体
_THINK_PATTERN = re.compile(
    r"<think[^>]*>.*?</think>\s*|"
    r"<thinking[^>]*>.*?</thinking>\s*|"
    r"<RESPOND>.*?</RESPOND>\s*",
    re.DOTALL | re.IGNORECASE,
)

logger = get_logger(__name__)


def _parse_json_from_text(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象，容错处理"""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning(f"无法解析 JSON，使用原始文本作为 summary")
    return {"summary": text, "key_events": [], "character_changes": [], "foreshadowing": []}


async def generate_summary(
    chapter_content: str,
    chapter_number: int,
) -> dict:
    """生成章节摘要，提取关键信息（prompt 模板可配置）"""
    system_prompt = await format_prompt("summarizer_chapter_system")
    user_prompt = await format_prompt(
        "summarizer_chapter_user",
        chapter_number=chapter_number,
        chapter_content=chapter_content,
    )

    try:
        raw = await call_llm(system_prompt, user_prompt)
        result = _parse_json_from_text(_THINK_PATTERN.sub("", raw))
        result.setdefault("summary", raw[:300])
        result.setdefault("key_events", [])
        result.setdefault("character_changes", [])
        result.setdefault("foreshadowing", [])
        logger.info(
            f"摘要生成成功: chapter={chapter_number}, "
            f"events={len(result['key_events'])}, "
            f"char_changes={len(result['character_changes'])}, "
            f"foreshadowing={len(result['foreshadowing'])}"
        )
        return result
    except Exception as e:
        logger.error(f"摘要生成失败: {e}", exc_info=True)
        raise


async def update_global_summary(
    current_summary: str,
    new_chapter_summary: str,
    chapter_number: int,
) -> str:
    """更新全局滚动摘要（prompt 模板可配置）"""
    system_prompt = await format_prompt("summarizer_global_system")
    user_prompt = await format_prompt(
        "summarizer_global_user",
        current_summary=current_summary if current_summary else "（尚无全局摘要，这是第一章）",
        new_chapter_summary=new_chapter_summary,
        chapter_number=chapter_number,
    )

    try:
        updated = await call_llm(system_prompt, user_prompt)
        return updated
    except Exception as e:
        logger.error(f"全局摘要更新失败: {e}", exc_info=True)
        return current_summary


async def generate_chapter_title(chapter_content: str, chapter_number: int) -> str:
    """根据章节正文自动生成标题（prompt 模板可配置）"""
    system_prompt = await format_prompt("summarizer_title_system")
    user_prompt = await format_prompt(
        "summarizer_title_user",
        chapter_number=chapter_number,
        chapter_content_preview=chapter_content[:800],
    )

    try:
        raw = await call_llm(system_prompt, user_prompt)
        title = _THINK_PATTERN.sub("", raw).strip()
        title = title.strip('"「」\'""').strip()
        if len(title) > 20:
            title = title[:20]
        logger.info(f"章节标题生成: chapter={chapter_number}, title={title}")
        return title
    except Exception as e:
        logger.error(f"章节标题生成失败: {e}", exc_info=True)
        return ""
