"""规划Agent：生成三层大纲体系（prompt 模板可配置）"""

import json
import re
from datetime import datetime, timezone

from bson import ObjectId

from ..core.database import get_mongodb
from ..core.llm import call_llm
from ..services.prompt_service import format_prompt
from ..utils.logger import get_logger

def _repair_truncated_json(text: str) -> str | None:
    """尝试修复被截断的 JSON（LLM 输出超 token 限制时常见）"""
    # 策略：从后往前找到最后一个完整的 volume_outline 对象结束标记 "},
    # 或完整的 key-value 对，然后补全剩余结构

    # 移除末尾不完整的片段（如截断在字符串中间）
    # 找到最后一个完整的 JSON 结构边界
    last_good = 0
    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth <= 0:
                last_good = i + 1

    if last_good > 0 and depth <= 0:
        # 找到了完整的顶层结构结束
        return text[:last_good]

    # 没找到完整结束，尝试在最后一个 } 处截断并补全
    last_brace = text.rfind("}")
    if last_brace > 0:
        truncated = text[:last_brace + 1]
        # 统计未闭合的括号
        open_braces = truncated.count("{") - truncated.count("}")
        open_brackets = truncated.count("[") - truncated.count("]")
        truncated += "]" * open_brackets + "}" * open_braces
        return truncated

    return None


def _regex_extract_outline_json(text: str) -> dict:
    """当 JSON 解析完全失败时，用正则提取关键字段（容错恢复）"""
    result: dict = {}

    # 提取 full_outline：匹配 "full_outline": "..." 中的内容
    full_match = re.search(
        r'"full_outline"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL
    )
    if full_match:
        result["full_outline"] = full_match.group(1)
    else:
        # 尝试更宽松的匹配：取 "full_outline" 之后到下一个已知字段之前
        full_match = re.search(
            r'"full_outline"\s*:\s*"(.+?)(?:"\s*[,}]|\s*"volume_outlines")',
            text, re.DOTALL
        )
        if full_match:
            result["full_outline"] = full_match.group(1).strip()

    # 提取 volume_outlines 数组中的每个对象
    volumes: list[dict] = []
    vol_pattern = re.compile(
        r'"volume_number"\s*:\s*(\d+)\s*,\s*'
        r'"volume_title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
        r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
        re.DOTALL,
    )
    for m in vol_pattern.finditer(text):
        volumes.append({
            "volume_number": int(m.group(1)),
            "volume_title": m.group(2),
            "content": m.group(3),
        })

    if volumes:
        result["volume_outlines"] = volumes

    return result


logger = get_logger(__name__)


def _extract_json(text: str) -> dict:
    """从 LLM 响应中提取 JSON（兼容 markdown 代码块和常见格式错误）"""
    # 1. 去除 markdown 代码块包裹
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)

    text = text.strip()

    # 2. 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. 常见修复：去除尾部逗号、控制字符
    fixed = text
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    fixed = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 4. 尝试从最外层 {} 提取
    start = fixed.find("{")
    end = fixed.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(fixed[start:end + 1])
        except json.JSONDecodeError:
            pass

    # 5. LLM 截断修复：从后向前找到最后一个完整的 key-value，补上 }]}
    if start != -1:
        truncated = fixed[start:]
        # 找到最后一个未被转义的双引号字符串结束位置
        # 简单策略：从后往前找最后一个 "volume_title" 或 "content" 等字段结束
        last_complete = _repair_truncated_json(truncated)
        if last_complete:
            try:
                return json.loads(last_complete)
            except json.JSONDecodeError:
                pass

    # 6. 最终兜底：用正则提取关键字段，不抛异常
    logger.warning(f"JSON 解析全部失败，尝试正则提取，原文前200字符: {text[:200]}")
    return _regex_extract_outline_json(text)


async def parse_existing_outline(outline_text: str) -> dict:
    """解析用户粘贴的已有大纲文本（prompt 模板可配置）"""
    system_prompt = await format_prompt("planner_parse_system")
    user_prompt = await format_prompt(
        "planner_parse_user",
        outline_text=outline_text,
    )

    response = await call_llm(system_prompt, user_prompt, max_tokens=16384)
    return _extract_json(response)


async def _generate_volume_outlines(
    novel_config: dict, char_text: str, volume_count: int
) -> tuple[str, list[dict]]:
    """第一阶段：生成全书总纲 + 分卷大纲（prompt 模板可配置）"""
    chapter_count = novel_config["chapter_count"]

    system_prompt = await format_prompt(
        "planner_volume_system",
        volume_count=volume_count,
    )
    user_prompt = await format_prompt(
        "planner_volume_user",
        title=novel_config["title"],
        genre=novel_config["genre"],
        style=novel_config["style"],
        world_setting=novel_config["world_setting"],
        chapter_count=chapter_count,
        char_text=char_text,
        volume_count=volume_count,
    )

    response = await call_llm(system_prompt, user_prompt, max_tokens=8192)
    data = _extract_json(response)
    full_outline = data.get("full_outline", response)
    volume_outlines = data.get("volume_outlines", [])

    if len(volume_outlines) < volume_count:
        for v in range(1, volume_count + 1):
            if not any(vo.get("volume_number") == v for vo in volume_outlines):
                start_ch = (v - 1) * 10 + 1
                end_ch = min(v * 10, chapter_count)
                volume_outlines.append({
                    "volume_number": v,
                    "volume_title": f"第{v}卷",
                    "content": f"第{v}卷(第{start_ch}-{end_ch}章)",
                })
        volume_outlines.sort(key=lambda x: x["volume_number"])

    return full_outline, volume_outlines


async def _generate_chapter_outlines_for_volume(
    novel_config: dict,
    char_text: str,
    volume_number: int,
    volume_outline: dict,
    chapter_start: int,
    chapter_end: int,
) -> list[dict]:
    """第二阶段：为单个分卷生成逐章细纲（prompt 模板可配置）"""
    chapter_count = chapter_end - chapter_start + 1
    volume_title = volume_outline.get("volume_title", f"第{volume_number}卷")
    volume_content = volume_outline.get("content", "")

    system_prompt = await format_prompt(
        "planner_chapter_system",
        volume_number=volume_number,
        chapter_count=chapter_count,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
    )
    user_prompt = await format_prompt(
        "planner_chapter_user",
        title=novel_config["title"],
        genre=novel_config["genre"],
        style=novel_config["style"],
        world_setting=novel_config["world_setting"],
        char_text=char_text,
        volume_number=volume_number,
        volume_title=volume_title,
        volume_content=volume_content,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
    )

    response = await call_llm(system_prompt, user_prompt, max_tokens=8192)
    data = _extract_json(response)
    return data.get("chapter_outlines", [])


async def generate_outline(project_id: str, novel_config: dict):
    """生成三层大纲：全书总纲 -> 分卷大纲 -> 逐章细纲（分批生成）"""
    db = await get_mongodb()

    await _update_outline_status(db, project_id, "generating")

    cursor = db["characters"].find({"project_id": project_id})
    characters = []
    async for char in cursor:
        characters.append(
            f"- {char['name']}({char['role_type']}): {char['personality']}, {char['background']}"
        )
    char_text = "\n".join(characters) if characters else "暂无角色设定"

    chapter_count = novel_config["chapter_count"]
    volume_count = (chapter_count + 9) // 10

    try:
        logger.info(f"[大纲] 第一阶段：生成全书总纲 + 分卷大纲: project_id={project_id}")
        full_outline, volume_outlines = await _generate_volume_outlines(
            novel_config, char_text, volume_count
        )
        logger.info(f"[大纲] 分卷大纲生成完成: {len(volume_outlines)} 卷")

        all_chapter_outlines = []
        for vol in volume_outlines:
            v = vol["volume_number"]
            start_ch = (v - 1) * 10 + 1
            end_ch = min(v * 10, chapter_count)
            logger.info(f"[大纲] 第二阶段：生成第 {v} 卷章节细纲 (第{start_ch}-{end_ch}章)")

            chapters = await _generate_chapter_outlines_for_volume(
                novel_config, char_text, v, vol, start_ch, end_ch
            )
            all_chapter_outlines.extend(chapters)
            logger.info(f"[大纲] 第 {v} 卷章节细纲生成完成: {len(chapters)} 章")

        chapter_outlines = all_chapter_outlines

        if len(chapter_outlines) < chapter_count:
            existing_nums = {ch["chapter_number"] for ch in chapter_outlines}
            for i in range(1, chapter_count + 1):
                if i not in existing_nums:
                    chapter_outlines.append({
                        "chapter_number": i,
                        "title": "",
                        "content": "待补充",
                    })
            chapter_outlines.sort(key=lambda x: x["chapter_number"])

        logger.info(f"大纲解析成功: {len(chapter_outlines)} 章, {len(volume_outlines)} 卷")

    except Exception as e:
        logger.warning(f"大纲生成或解析失败，使用 fallback: {e}")
        full_outline = "大纲生成异常"
        chapter_outlines = [
            {"chapter_number": i, "title": "", "content": "待补充"}
            for i in range(1, chapter_count + 1)
        ]
        volume_outlines = [
            {"volume_number": v, "volume_title": f"第{v}卷", "content": f"第{v}卷"}
            for v in range(1, volume_count + 1)
        ]

    outline_doc = {
        "project_id": project_id,
        "full_outline": full_outline,
        "volume_outlines": volume_outlines,
        "chapter_outlines": chapter_outlines,
        "version": 1,
        "created_at": datetime.now(timezone.utc),
    }

    existing = await db["outlines"].find_one({"project_id": project_id})
    if existing:
        await db["outlines"].update_one(
            {"project_id": project_id},
            {"$set": outline_doc},
        )
    else:
        await db["outlines"].insert_one(outline_doc)

    await _update_outline_status(db, project_id, "review")
    logger.info(f"大纲生成完成，等待审核: {project_id}")


async def _update_outline_status(db, project_id: str, status: str):
    """更新项目的大纲生成状态"""
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"outline_status": status}},
    )
