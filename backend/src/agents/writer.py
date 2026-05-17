"""写作Agent：依据细纲+人设+摘要+前章摘要创作正文"""

import re
from typing import Awaitable, Callable

from ..core.llm import call_llm, call_llm_stream
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 匹配 <think>...</think> 及其变体（含换行）
_THINK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)

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


def _build_system_prompt(style: str, words_per_chapter: int, audit_feedback: str = "") -> str:
    """构建写作 system prompt"""
    prompt = f"""你是一位专业的小说作家。根据提供的大纲、人设和前文信息，创作高质量的小说正文。

## 核心写作规则

1. **大纲是最高指令**：细纲中描述的每一个情节点都必须在正文中体现，不得遗漏、替换或自行发挥超出细纲范围的内容
2. **人设不崩**：人物行为、对话、决策必须与其性格和背景设定一致
3. **剧情连贯**：承接前文摘要，不得出现与已发生事件矛盾的内容
4. **文风统一**：{style}
5. **目标字数**：{words_per_chapter}字左右
6. **节奏把控**：语句流畅，无灌水，无生硬描写
7. **自然收束**：章节结尾必须是完整的场景结束，不得中途截断
8. **内容合规**：避免血腥暴力、色情擦边、政治敏感内容
9. **使用中文**创作"""

    if audit_feedback:
        prompt += f"""

## 上次审核未通过 —— 必须修正以下问题

{audit_feedback}

重写时必须针对上述问题逐一修正，同时保持细纲要求的剧情不变。"""

    return prompt


def _build_user_prompt(
    world_setting: str,
    character_info: str,
    global_summary: str,
    previous_summary: str,
    recalled_memories: str,
    chapter_outline: str,
    chapter_number: int,
) -> str:
    """构建写作 user prompt，将细纲拆分为检查清单格式"""
    parts = []

    parts.append(f"世界观：{world_setting}")
    parts.append(f"\n角色设定：\n{character_info}")

    if global_summary:
        parts.append(f"\n前文摘要（全局）：\n{global_summary}")
    if previous_summary:
        parts.append(f"\n上一章摘要：\n{previous_summary}")
    if recalled_memories:
        parts.append(f"\n相关前文记忆：\n{recalled_memories}")

    # 将细纲以高亮格式呈现，强调为必须覆盖的检查清单
    parts.append(f"""
═══════════════════════════════════════
当前创作：第{chapter_number}章
本章细纲（以下每个情节点都必须在正文中完整体现）：
═══════════════════════════════════════
{chapter_outline}
═══════════════════════════════════════""")

    parts.append(f"""
请创作第{chapter_number}章正文。
- 确保上述细纲中的每个情节点都有对应的正文段落
- 章节有完整的开头、发展和结尾
- 与上一章自然衔接
- 不要在正文中输出章节号标题（如"第X章"或"# 第X章：标题"），直接以场景描写或对话开始正文
- 不要在正文末尾添加任何元数据、总结或分隔线""")

    return "\n".join(parts)


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
    system_prompt = _build_system_prompt(style, words_per_chapter, audit_feedback)
    user_prompt = _build_user_prompt(
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
    system_prompt = _build_system_prompt(style, words_per_chapter, audit_feedback)
    user_prompt = _build_user_prompt(
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
