"""写作Agent：依据细纲+人设+摘要+前章摘要创作正文（prompt 模板可配置）"""

import re
from typing import Awaitable, Callable

from ..core.llm import call_llm, call_llm_stream
from ..services.prompt_service import format_prompt
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 匹配 <think>...</think>、 response... 及其变体（含换行），兼容 Qwen / DeepSeek 等模型
_THINK_PATTERN = re.compile(
    r"<think[^>]*>.*?</think>\s*|"
    r"<thinking[^>]*>.*?</thinking>\s*|"
    r"<RESPOND>.*?</RESPOND>\s*",
    re.DOTALL | re.IGNORECASE,
)

# 精确匹配 "——第X章 完——" 及其后的全部元数据
_CHAPTER_END_PATTERN = re.compile(
    r"\n+\*{0,2}[-—]{1,3}\s*第\d+章\s*[完终]\s*[-—]{1,3}\*{0,2}\s*\n+.*$",
    re.DOTALL,
)

# 匹配正文开头的章节标题（如 "# 第4章：气场全开" 或 "第5章\n"），用于剥离
_CHAPTER_HEADER_PATTERN = re.compile(
    r"^\s*#{0,3}\s*第[\d零一二三四五六七八九十百千]+章(?:[：:\s]+[^\n]*)?\n+",
)


def _strip_meta(text: str) -> str:
    """移除 LLM 输出中的思考过程标签、章节开头标题和章节末尾元数据总结"""
    cleaned = _THINK_PATTERN.sub("", text).strip()
    if cleaned != text.strip():
        logger.info("已过滤 LLM 思考过程标签")

    # 剥离正文开头的章节标题（如 "# 第4章：气场全开"）
    header_result = _CHAPTER_HEADER_PATTERN.sub("", cleaned)
    if header_result != cleaned:
        logger.info("已过滤正文开头的章节标题")
        cleaned = header_result.strip()

    # 精确匹配 "——第X章 完——" 及之后内容
    result = _CHAPTER_END_PATTERN.sub("", cleaned)
    if result != cleaned:
        logger.info("已过滤章节末尾元数据（第X章完标记）")
        cleaned = result.strip()

    return cleaned


async def _build_system_prompt(style: str, words_per_chapter: int, audit_feedback: str = "") -> str:
    """构建写作 system prompt（从 PromptService 加载模板）"""
    min_words = words_per_chapter
    max_words = int(words_per_chapter * 1.3)
    prompt = await format_prompt(
        "writer_system",
        style=style,
        min_words=min_words,
        max_words=max_words,
    )

    if audit_feedback:
        feedback_section = await format_prompt(
            "writer_system_audit_feedback",
            audit_feedback=audit_feedback,
        )
        prompt += feedback_section

    return prompt


async def _build_user_prompt(
    world_setting: str,
    character_info: str,
    global_summary: str,
    previous_summary: str,
    recalled_memories: str,
    chapter_outline: str,
    chapter_number: int,
) -> str:
    """构建写作 user prompt（从 PromptService 加载模板）"""
    return await format_prompt(
        "writer_user",
        world_setting=world_setting,
        character_info=character_info,
        global_summary=global_summary or "暂无",
        previous_summary=previous_summary or "暂无",
        recalled_memories=recalled_memories or "暂无",
        chapter_outline=chapter_outline,
        chapter_number=chapter_number,
    )


async def write_chapter(
    chapter_outline: str,
    character_info: str,
    global_summary: str,
    previous_summary: str,
    recalled_memories: str,
    world_setting: str,
    style: str,
    words_per_chapter: int,
    chapter_number: int,
    audit_feedback: str = "",
    temperature: float = 0.7,
) -> str:
    """创作章节正文"""
    system_prompt = await _build_system_prompt(style, words_per_chapter, audit_feedback)
    user_prompt = await _build_user_prompt(
        world_setting, character_info, global_summary,
        previous_summary, recalled_memories, chapter_outline, chapter_number,
    )

    try:
        content = await call_llm(system_prompt, user_prompt, temperature=temperature)
        return _strip_meta(content)
    except Exception as e:
        logger.error(f"章节创作失败: {e}", exc_info=True)
        raise


async def write_chapter_stream(
    chapter_outline: str,
    character_info: str,
    global_summary: str,
    previous_summary: str,
    recalled_memories: str,
    world_setting: str,
    style: str,
    words_per_chapter: int,
    chapter_number: int,
    on_token: Callable[[str], Awaitable[None]] | None = None,
    audit_feedback: str = "",
    temperature: float = 0.7,
) -> str:
    """创作章节正文（流式），每个 token 通过 on_token 回调推送"""
    system_prompt = await _build_system_prompt(style, words_per_chapter, audit_feedback)
    user_prompt = await _build_user_prompt(
        world_setting, character_info, global_summary,
        previous_summary, recalled_memories, chapter_outline, chapter_number,
    )

    try:
        content_parts = []
        async for token in call_llm_stream(system_prompt, user_prompt, temperature=temperature):
            content_parts.append(token)
            if on_token:
                await on_token(token)
        return _strip_meta("".join(content_parts))
    except Exception as e:
        logger.error(f"章节创作失败: {e}", exc_info=True)
        raise
